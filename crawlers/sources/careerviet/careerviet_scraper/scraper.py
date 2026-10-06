"""
scraper.py - Logic điều khiển Browser & Crawling
Sử dụng Playwright (asyncio) với Semaphore, Rate Limiting,
Retry cơ chế, và xử lý đầy đủ các exception.
"""

import asyncio
import logging
import random
import time
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

from . import config
from .parser import extract_job_links_from_listing, has_next_page, JobDetailParser
from .pipeline import CheckpointManager, Deduplicator, OutputManager, ErrorLogger, StatsReporter

logger = logging.getLogger(__name__)


# ============================================================
# UTILITY
# ============================================================

def _random_delay(min_s: float = None, max_s: float = None):
    """Delay đồng bộ (dùng trong async context với asyncio.sleep)."""
    min_s = min_s or config.DELAY_MIN
    max_s = max_s or config.DELAY_MAX
    return random.uniform(min_s, max_s)


async def _async_delay(min_s: float = None, max_s: float = None):
    """Await delay ngẫu nhiên để tránh phát hiện bot."""
    delay = _random_delay(min_s, max_s)
    await asyncio.sleep(delay)


def _build_page_url(base_category_url: str, page: int) -> str:
    """
    Tạo URL trang listing theo số trang của CareerViet:
      Trang 1: /viec-lam/cntt-phan-mem-c1-vi.html
      Trang 2: /viec-lam/cntt-phan-mem-c1-trang-2-vi.html
      Trang N: /viec-lam/cntt-phan-mem-c1-trang-N-vi.html
    """
    if page <= 1:
        return config.BASE_URL + base_category_url

    # CareerViet pattern: chèn -trang-N vào trước -vi.html hoặc đuôi .html
    if "-vi.html" in base_category_url:
        paged_path = base_category_url.replace("-vi.html", f"-trang-{page}-vi.html")
    elif ".html" in base_category_url:
        paged_path = base_category_url.replace(".html", f"-trang-{page}.html")
    else:
        paged_path = f"{base_category_url}?page={page}"

    return config.BASE_URL + paged_path


# ============================================================
# BROWSER FACTORY
# ============================================================

class BrowserFactory:
    """Khởi tạo và quản lý Playwright Browser + Context."""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    async def start(self):
        """Khởi động Playwright và mở Chromium headless."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=config.BROWSER_ARGS,
        )
        logger.info("[Browser] Chromium đã khởi động.")
        await self._create_context()

    async def _create_context(self):
        """Tạo BrowserContext với cấu hình anti-detect."""
        user_agent = random.choice(config.USER_AGENTS)
        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport=config.VIEWPORT,
            locale=config.LOCALE,
            timezone_id=config.TIMEZONE,
            extra_http_headers=config.EXTRA_HEADERS,
            # Ẩn dấu hiệu automation
            java_script_enabled=True,
        )
        # Script inject để ẩn webdriver flag
        await self._context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)
        logger.info(f"[Browser] Context tạo với UA: {user_agent[:60]}...")

    async def new_page(self) -> Page:
        """Tạo tab mới từ context hiện tại."""
        if self._context is None:
            raise RuntimeError("Browser context chưa được khởi tạo.")
        page = await self._context.new_page()
        page.set_default_timeout(config.PAGE_LOAD_TIMEOUT)
        return page

    async def reset_context(self):
        """Tạo lại context (đổi UA, xóa cookies) khi bị chặn."""
        if self._context:
            await self._context.close()
        await self._create_context()
        logger.info("[Browser] Context đã reset.")

    async def stop(self):
        """Đóng browser và giải phóng tài nguyên."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("[Browser] Đã đóng Playwright.")


# ============================================================
# PAGE FETCHER
# ============================================================

class PageFetcher:
    """
    Fetch HTML của một URL với cơ chế retry và anti-detection.
    """

    def __init__(self, browser_factory: BrowserFactory):
        self.factory = browser_factory
        self._consecutive_errors = 0

    async def fetch(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        retries: int = None,
    ) -> Optional[str]:
        """
        Tải trang và trả về HTML nguồn.
        
        Args:
            url: URL cần tải
            wait_for_selector: CSS selector đợi xuất hiện trước khi lấy HTML
            retries: Số lần retry (mặc định từ config)
            
        Returns:
            HTML string hoặc None nếu thất bại
        """
        retries = retries if retries is not None else config.MAX_RETRIES
        page: Optional[Page] = None

        for attempt in range(1, retries + 1):
            try:
                page = await self.factory.new_page()

                # Navigate với networkidle để đảm bảo JS render xong
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT,
                )

                # Kiểm tra HTTP status
                if response and response.status == 404:
                    logger.warning(f"[Fetcher] 404 Not Found: {url}")
                    return None

                if response and response.status in (403, 429, 503):
                    logger.warning(
                        f"[Fetcher] HTTP {response.status} – Bị chặn, "
                        f"reset context và đợi... (attempt {attempt}/{retries})"
                    )
                    await self.factory.reset_context()
                    await asyncio.sleep(config.RETRY_DELAY * attempt)
                    continue

                # Đợi selector quan trọng (nếu có)
                if wait_for_selector:
                    try:
                        await page.wait_for_selector(
                            wait_for_selector,
                            timeout=config.ELEMENT_TIMEOUT,
                        )
                    except PlaywrightTimeoutError:
                        logger.debug(f"[Fetcher] Selector '{wait_for_selector}' không tìm thấy: {url}")

                # Scroll xuống để trigger lazy-load
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
                await asyncio.sleep(0.5)

                html = await page.content()
                self._consecutive_errors = 0
                return html

            except PlaywrightTimeoutError:
                logger.warning(
                    f"[Fetcher] Timeout (attempt {attempt}/{retries}): {url}"
                )
                self._consecutive_errors += 1

            except PlaywrightError as pe:
                logger.error(
                    f"[Fetcher] Playwright error (attempt {attempt}/{retries}): {pe} | {url}"
                )
                self._consecutive_errors += 1
                # Nếu lỗi context, reset
                if "Target closed" in str(pe) or "Session closed" in str(pe):
                    await self.factory.reset_context()

            except Exception as exc:
                logger.error(
                    f"[Fetcher] Lỗi không xác định (attempt {attempt}/{retries}): {exc} | {url}"
                )
                self._consecutive_errors += 1

            finally:
                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass
                    page = None

            # Exponential backoff giữa các retry
            if attempt < retries:
                backoff = config.RETRY_DELAY * attempt + random.uniform(0, 2)
                logger.info(f"[Fetcher] Retry sau {backoff:.1f}s...")
                await asyncio.sleep(backoff)

        # Nếu quá nhiều lỗi liên tiếp → reset context
        if self._consecutive_errors >= 5:
            logger.warning("[Fetcher] Quá nhiều lỗi liên tiếp, reset context...")
            await self.factory.reset_context()
            self._consecutive_errors = 0

        return None


# ============================================================
# LISTING CRAWLER: Lấy URL từ trang danh sách
# ============================================================

class ListingCrawler:
    """
    Duyệt qua các trang listing của một danh mục,
    thu thập toàn bộ job URL.
    """

    def __init__(self, fetcher: PageFetcher, checkpoint: CheckpointManager):
        self.fetcher = fetcher
        self.checkpoint = checkpoint

    async def crawl_category(self, category: dict) -> list[str]:
        """
        Crawl toàn bộ trang listing của một danh mục.
        
        Args:
            category: Dict { "name": str, "url_path": str, ... }
            
        Returns:
            Danh sách URL việc làm (đã deduplicated trong category)
        """
        cat_name = category["name"]

        # Resume: nếu đã lấy xong listing
        if self.checkpoint.is_category_listing_done(cat_name):
            queued = self.checkpoint.get_queued_urls(cat_name)
            logger.info(
                f"[Listing] Resume '{cat_name}': "
                f"{len(queued)} URL đã có trong checkpoint."
            )
            return queued

        all_urls: list[str] = []
        seen_on_listing: set[str] = set()
        page_num = 1
        consecutive_empty = 0

        logger.info(f"[Listing] Bắt đầu crawl danh mục: {cat_name}")

        while True:
            page_url = _build_page_url(category["url_path"], page_num)
            logger.info(f"[Listing] Trang {page_num}: {page_url}")

            html = await self.fetcher.fetch(
                page_url,
                wait_for_selector="div.job-item, .job-list",
            )

            if not html:
                logger.warning(f"[Listing] Không lấy được HTML trang {page_num}. Dừng.")
                break

            # Bóc tách link
            new_links = extract_job_links_from_listing(html)
            new_unique = [u for u in new_links if u not in seen_on_listing]

            if not new_unique:
                consecutive_empty += 1
                logger.warning(
                    f"[Listing] Trang {page_num} trống "
                    f"({consecutive_empty} lần liên tiếp)."
                )
                if consecutive_empty >= 2:
                    logger.info(f"[Listing] Dừng danh mục '{cat_name}' sau 2 trang trống.")
                    break
            else:
                consecutive_empty = 0
                for u in new_unique:
                    seen_on_listing.add(u)
                all_urls.extend(new_unique)
                logger.info(
                    f"[Listing] Trang {page_num} → {len(new_unique)} URL mới "
                    f"(tổng: {len(all_urls)})"
                )

            # Kiểm tra có trang tiếp không
            if not has_next_page(html):
                logger.info(f"[Listing] Đã đến trang cuối của '{cat_name}'.")
                break

            page_num += 1
            await _async_delay()  # Rate limiting

        # Lưu vào checkpoint
        self.checkpoint.set_queued_urls(cat_name, all_urls)
        self.checkpoint.mark_category_listing_done(cat_name)
        logger.info(f"[Listing] '{cat_name}' hoàn thành: {len(all_urls)} URL.")

        return all_urls


# ============================================================
# DETAIL CRAWLER: Cào chi tiết từng job
# ============================================================

class DetailCrawler:
    """
    Cào nội dung chi tiết của từng job URL.
    Sử dụng Semaphore để giới hạn concurrent requests.
    """

    def __init__(
        self,
        fetcher: PageFetcher,
        checkpoint: CheckpointManager,
        deduplicator: Deduplicator,
        output_manager: OutputManager,
        error_logger: ErrorLogger,
        stats_reporter: StatsReporter,
        all_jobs: list[dict],
    ):
        self.fetcher       = fetcher
        self.checkpoint    = checkpoint
        self.dedup         = deduplicator
        self.output        = output_manager
        self.error_logger  = error_logger
        self.stats         = stats_reporter
        self.all_jobs      = all_jobs
        self._semaphore    = asyncio.Semaphore(config.MAX_CONCURRENT_PAGES)

    async def crawl_url(self, url: str, category_name: str):
        """
        Cào một URL job. Được gọi song song qua Semaphore.
        """
        async with self._semaphore:
            # Bỏ qua nếu đã cào
            if self.checkpoint.is_url_crawled(url):
                logger.debug(f"[Detail] Skip (đã cào): {url}")
                return

            logger.info(f"[Detail] Cào: {url}")
            html = await self.fetcher.fetch(
                url,
                wait_for_selector="div.job-desc, h1.title",
            )

            if not html:
                logger.error(f"[Detail] Không lấy được HTML: {url}")
                self.error_logger.log(url, "Không lấy được HTML", category_name)
                self.checkpoint.mark_url_crawled(url, success=False)
                self.stats.record(category_name, success=False)
                self.checkpoint.save()
                await _async_delay()
                return

            # Parse
            parser = JobDetailParser(html, url, category_name)
            record = parser.parse()

            # Deduplication
            if self.dedup.is_duplicate(record):
                logger.debug(f"[Detail] Trùng lặp, bỏ qua: {record.get('job_id')} | {url}")
                self.checkpoint.mark_url_crawled(url, success=True)
                self.checkpoint.save()
                await _async_delay()
                return

            # Lưu record
            self.dedup.mark_seen(record)
            self.all_jobs.append(record)
            self.output.append(record, self.all_jobs)
            self.checkpoint.mark_url_crawled(url, success=True)
            self.stats.record(category_name, success=True)

            logger.info(
                f"[Detail] ✓ [{record.get('job_id')}] "
                f"{record.get('title', 'N/A')[:50]} | "
                f"{record.get('company_name', 'N/A')[:30]}"
            )

            # Lưu checkpoint định kỳ
            if len(self.all_jobs) % 20 == 0:
                self.checkpoint.save()

            await _async_delay()

    async def crawl_batch(self, urls: list[str], category_name: str):
        """
        Cào một batch URL thuộc cùng danh mục.
        Dùng asyncio.gather với Semaphore để kiểm soát concurrent.
        """
        tasks = [
            self.crawl_url(url, category_name)
            for url in urls
        ]

        # Chia batch thành chunk để tránh tạo quá nhiều task cùng lúc
        chunk_size = 20
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i + chunk_size]
            await asyncio.gather(*chunk, return_exceptions=True)
            logger.info(
                f"[Detail] Hoàn thành chunk {i//chunk_size + 1} "
                f"({min(i + chunk_size, len(tasks))}/{len(tasks)} URLs)"
            )


# ============================================================
# MAIN SCRAPER ORCHESTRATOR
# ============================================================

class CareerVietScraper:
    """
    Orchestrator tổng thể điều phối toàn bộ quá trình scraping.
    """

    def __init__(self):
        from . import config as cfg

        self.browser_factory = BrowserFactory()
        self.checkpoint      = CheckpointManager(cfg.CHECKPOINT_FILE)
        self.dedup           = Deduplicator()
        self.output          = OutputManager(cfg.OUTPUT_FILE)
        self.error_logger    = ErrorLogger(cfg.ERROR_LOG_FILE)
        self.stats           = StatsReporter()

        # Load dữ liệu cũ (resume mode)
        self.all_jobs: list[dict] = self.output.load_existing()
        self.dedup.load_from_existing_output(cfg.OUTPUT_FILE)
        self.dedup.load_from_checkpoint(self.checkpoint)

    async def run(self):
        """Entry point bất đồng bộ – chạy toàn bộ pipeline."""
        self.stats.start()
        start_wall = time.time()

        try:
            await self.browser_factory.start()
            fetcher = PageFetcher(self.browser_factory)

            listing_crawler = ListingCrawler(fetcher, self.checkpoint)
            detail_crawler  = DetailCrawler(
                fetcher=fetcher,
                checkpoint=self.checkpoint,
                deduplicator=self.dedup,
                output_manager=self.output,
                error_logger=self.error_logger,
                stats_reporter=self.stats,
                all_jobs=self.all_jobs,
            )

            # ---- PHASE 1: Thu thập URL listing ----
            logger.info("=" * 50)
            logger.info("PHASE 1: Thu thập URL từ trang listing...")
            logger.info("=" * 50)

            all_category_urls: dict[str, list[str]] = {}

            for category in config.TARGET_CATEGORIES:
                cat_name = category["name"]
                urls = await listing_crawler.crawl_category(category)
                all_category_urls[cat_name] = urls
                logger.info(f"  ► {cat_name}: {len(urls)} URLs")
                await _async_delay(2, 5)  # Delay dài hơn giữa các category

            total_urls = sum(len(v) for v in all_category_urls.values())
            logger.info(f"\nTổng URL thu thập: {total_urls}")

            # ---- PHASE 2: Cào chi tiết từng job ----
            logger.info("\n" + "=" * 50)
            logger.info("PHASE 2: Cào nội dung chi tiết từng job...")
            logger.info("=" * 50)

            for category in config.TARGET_CATEGORIES:
                cat_name = category["name"]
                urls = all_category_urls.get(cat_name, [])

                if not urls:
                    logger.warning(f"[Main] Không có URL cho '{cat_name}', bỏ qua.")
                    continue

                # Filter bỏ URL đã cào
                pending_urls = [u for u in urls if not self.checkpoint.is_url_crawled(u)]
                logger.info(
                    f"\n[Main] Danh mục: {cat_name} | "
                    f"Tổng: {len(urls)} | Cần cào: {len(pending_urls)}"
                )

                if not pending_urls:
                    logger.info(f"[Main] '{cat_name}' đã hoàn thành trước đó, bỏ qua.")
                    continue

                await detail_crawler.crawl_batch(pending_urls, cat_name)

            # ---- PHASE 3: Final flush & report ----
            logger.info("\n" + "=" * 50)
            logger.info("PHASE 3: Lưu dữ liệu cuối cùng...")
            logger.info("=" * 50)

            self.output.flush(self.all_jobs)
            self.checkpoint.save()

        except KeyboardInterrupt:
            logger.info("\n[Main] Người dùng dừng (Ctrl+C). Đang lưu dữ liệu...")
            self.output.flush(self.all_jobs)
            self.checkpoint.save()

        except Exception as exc:
            logger.critical(f"[Main] Lỗi nghiêm trọng: {exc}", exc_info=True)
            self.output.flush(self.all_jobs)
            self.checkpoint.save()

        finally:
            await self.browser_factory.stop()
            self.stats.stop()

            elapsed = time.time() - start_wall
            logger.info(
                f"\n[Main] Kết thúc. "
                f"Tổng thời gian: {elapsed/60:.1f} phút | "
                f"Đã lưu: {len(self.all_jobs)} records → {config.OUTPUT_FILE}"
            )

            self.stats.print_report()
