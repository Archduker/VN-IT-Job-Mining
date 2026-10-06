import os
import csv
import time
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager


def setup_driver():
    options = webdriver.ChromeOptions()

    # Thư mục profile riêng, KHÔNG dùng thư mục User Data mặc định của Chrome
    user_data_dir = r"C:\selenium_profile"
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--profile-directory=Default")

    # Giảm khả năng bị phát hiện là tự động hóa
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Một số tùy chọn giúp Chrome khởi động ổn định hơn trên Windows
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--remote-debugging-port=9222")

    # Selenium 4.6+ tự tải driver phù hợp, không cần webdriver_manager
    driver = webdriver.Chrome(options=options)
    return driver


# ===================== CODE CHÍNH =====================

# Mở trình duyệt (dùng profile đã đăng nhập)
driver = setup_driver()
driver.maximize_window()

wait = WebDriverWait(driver, 15)
driver.get("https://topdev.vn/viec-lam/tim-kiem")

jobs = []
seen_urls = set()
page = 1

try:
    while True:
        print(f"\nĐang thu thập trang {page}...")

        # Chờ các thẻ chứa tin tuyển dụng xuất hiện
        wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.w-full"))
        )
        time.sleep(2)

        containers = driver.find_elements(By.CSS_SELECTOR, "span.w-full")
        page_count = 0

        for container in containers:
            links = container.find_elements(
                By.CSS_SELECTOR, "a[href*='/viec-lam/']"
            )

            for title_link in links:
                href = title_link.get_attribute("href")
                title = title_link.text.strip()

                if not href or not title or href in seen_urls:
                    continue

                seen_urls.add(href)

                # Tên công ty
                company = ""
                try:
                    company = title_link.find_element(
                        By.XPATH, "./following-sibling::span[1]"
                    ).text.strip()
                except Exception:
                    pass

                # Mức lương
                salary = ""
                salary_elements = container.find_elements(
                    By.XPATH, ".//span[contains(@class, 'text-[#e4007f]')]"
                )
                if salary_elements:
                    salary = salary_elements[0].text.strip()

                # Địa điểm và hình thức làm việc
                location = ""
                job_type = ""
                grids = container.find_elements(
                    By.XPATH, ".//div[contains(@class, 'grid-cols-2')]"
                )
                if grids:
                    grid_spans = grids[0].find_elements(By.XPATH, "./span")
                    if len(grid_spans) >= 1:
                        location = grid_spans[0].text.strip()
                    if len(grid_spans) >= 2:
                        job_type = grid_spans[1].text.strip()

                # Các kỹ năng
                skill_links = container.find_elements(
                    By.CSS_SELECTOR, "a[href*='/jobs/search?keyword=']"
                )
                skills = list(dict.fromkeys(
                    link.text.strip()
                    for link in skill_links
                    if link.text.strip()
                ))

                # Thời gian đăng tuyển
                posted_date = ""
                for span in container.find_elements(By.TAG_NAME, "span"):
                    text_value = span.text.strip()
                    if any(word in text_value.lower() for word in [
                        "trước", "hôm nay", "ngày", "tuần", "tháng"
                    ]):
                        posted_date = text_value
                        break

                jobs.append({
                    "job_title": title,
                    "company": company,
                    "salary": salary,
                    "location": location,
                    "job_type": job_type,
                    "skills": ", ".join(skills),
                    "posted_date": posted_date,
                    "job_url": urljoin("https://topdev.vn", href)
                })

                page_count += 1

        print(f"Đã thu thập {page_count} tin mới.")
        print(f"Tổng số tin: {len(jobs)}")

        # Tìm vùng phân trang có class hidden md:block
        wrappers = driver.find_elements(
            By.XPATH,
            "//*[contains(concat(' ', normalize-space(@class), ' '), ' hidden ') "
            "and contains(concat(' ', normalize-space(@class), ' '), ' md:block ')]"
        )

        next_button = None

        for wrapper in wrappers:
            candidates = []
            if wrapper.tag_name in ["button", "a"]:
                candidates.append(wrapper)

            candidates.extend(
                wrapper.find_elements(By.XPATH, ".//button | .//a")
            )

            for candidate in candidates:
                text_value = (candidate.text or "").strip().lower()
                aria_label = (candidate.get_attribute("aria-label") or "").lower()
                title_value = (candidate.get_attribute("title") or "").lower()

                if (
                    text_value in ["next", "next page", "›", "»", "→"]
                    or "next" in aria_label
                    or "next" in title_value
                ):
                    next_button = candidate
                    break

            if next_button:
                break

        if next_button is None:
            print("Không tìm thấy nút Next. Đã hết trang.")
            break

        # Kiểm tra nút Next có bị vô hiệu hóa không
        disabled = next_button.get_attribute("disabled")
        aria_disabled = next_button.get_attribute("aria-disabled")
        classes = (next_button.get_attribute("class") or "").lower()

        if (
            disabled is not None
            or aria_disabled == "true"
            or "disabled" in classes.split()
        ):
            print("Nút Next đã bị vô hiệu hóa. Kết thúc.")
            break

        # Ghi nhận URL các tin hiện tại để phát hiện trang mới
        old_links = driver.find_elements(
            By.CSS_SELECTOR, "a[href*='/viec-lam/']"
        )
        old_hrefs = {link.get_attribute("href") for link in old_links}

        # Cuộn tới nút Next
        driver.execute_script(
            "arguments[0].scrollIntoView({block: 'center'});", next_button
        )
        time.sleep(1)

        # Thử click thông thường, nếu bị che thì dùng JavaScript
        try:
            wait.until(EC.element_to_be_clickable(next_button))
            next_button.click()
        except Exception as e:
            print(f"Click thông thường thất bại: {e.__class__.__name__}")
            print("Đang thử click bằng JavaScript...")
            driver.execute_script("arguments[0].click();", next_button)

        # Chờ danh sách công việc thay đổi
        try:
            wait.until(
                lambda d: any(
                    href not in old_hrefs
                    for href in d.execute_script("""
                        return Array.from(
                            document.querySelectorAll("a[href*='/viec-lam/']")
                        ).map(a => a.href);
                    """)
                )
            )
            print("Đã chuyển sang trang tiếp theo.")
            page += 1
        except TimeoutException:
            print("Không phát hiện dữ liệu mới sau khi nhấn Next.")
            break

finally:
    # Lưu dữ liệu đã thu thập
    if jobs:
        with open("topdev_jobs.csv", "w", newline="", encoding="utf-8-sig") as file:
            fieldnames = [
                "job_title", "company", "salary", "location",
                "job_type", "skills", "posted_date", "job_url"
            ]
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(jobs)

        print(f"\nHoàn tất: {len(jobs)} tin tuyển dụng.")
        print("Đã lưu vào topdev_jobs.csv")
    else:
        print("Không thu thập được dữ liệu.")

    driver.quit()