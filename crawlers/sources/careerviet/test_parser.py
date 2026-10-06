"""Kiểm tra nhanh logic parser và pipeline."""
from careerviet_scraper.parser import (
    extract_job_links_from_listing,
    has_next_page,
    JobDetailParser,
    extract_job_id,
)
from careerviet_scraper.pipeline import CheckpointManager, Deduplicator

# ── Test 1: extract_job_id ──────────────────────────────────
url1 = "https://careerviet.vn/vi/tim-viec-lam/data-engineer.35C541AE.html"
url2 = "https://careerviet.vn/vi/tim-viec-lam/software-dev.AABB1122.html"
assert extract_job_id(url1) == "35C541AE", f"Expected 35C541AE, got {extract_job_id(url1)}"
assert extract_job_id(url2) == "AABB1122"
print("✓ extract_job_id")

# ── Test 2: extract_job_links_from_listing ──────────────────
listing_html = """
<html><body>
  <div class="job-item">
    <a class="job-title" href="/vi/tim-viec-lam/python-developer.35C541AE.html">Python Dev</a>
  </div>
  <div class="job-item">
    <a class="job-title" href="/vi/tim-viec-lam/data-engineer.99A1B2C3.html">Data Eng</a>
  </div>
  <div class="job-item">
    <a class="job-title" href="/vi/tim-viec-lam/python-developer.35C541AE.html">Duplicate</a>
  </div>
  <ul class="pagination"><li class="next-page"><a href="?page=2">Tiep</a></li></ul>
</body></html>
"""
links = extract_job_links_from_listing(listing_html)
assert len(links) == 2, f"Expected 2 unique links, got {len(links)}"
assert "https://careerviet.vn/vi/tim-viec-lam/python-developer.35C541AE.html" in links
print(f"✓ extract_job_links_from_listing ({len(links)} links)")

# ── Test 3: has_next_page ───────────────────────────────────
assert has_next_page(listing_html) is True
no_next_html = "<html><body><div class='job-item'><a class='job-title' href='/vi/tim-viec-lam/dev.AABB11.html'>X</a></div></body></html>"
assert has_next_page(no_next_html) is False
print("✓ has_next_page")

# ── Test 4: JobDetailParser ─────────────────────────────────
detail_html = """
<html><body>
  <div class="job-desc">
    <h1 class="title">Senior Data Engineer</h1>
    <a class="employer job-company-name" href="/nha-tuyen-dung/techcorp.html">TechCorp VN</a>
  </div>
  <ul class="job-info">
    <li><label>Mức lương</label><span>25 Tr - 40 Tr VND</span></li>
    <li><label>Kinh nghiệm</label><span>3 - 5 Năm</span></li>
    <li><label>Cấp bậc</label><span>Trưởng nhóm</span></li>
    <li><label>Hạn nộp hồ sơ</label><span>31/10/2026</span></li>
    <li><label>Học vấn</label><span>Đại học</span></li>
    <li><label>Ngành nghề</label><span>CNTT - Phần mềm</span></li>
    <li><label>Hình thức làm việc</label><span>Toàn thời gian</span></li>
  </ul>
  <div class="detail-row reset-bullet">
    <h2>Mô tả công việc</h2>
    <ul>
      <li>Xây dựng data pipeline với Apache Spark</li>
      <li>Tối ưu hóa truy vấn SQL trên BigQuery</li>
    </ul>
  </div>
  <div class="detail-row reset-bullet">
    <h2>Yêu cầu công việc</h2>
    <ul>
      <li>3+ năm kinh nghiệm Python</li>
      <li>Thành thạo SQL, ETL, dbt</li>
    </ul>
  </div>
  <div class="detail-row reset-bullet">
    <h2>Quyền lợi</h2>
    <ul>
      <li>Lương thưởng cạnh tranh</li>
      <li>Bảo hiểm sức khỏe</li>
    </ul>
  </div>
  <div class="job-tags"><ul>
    <li><a>Python</a></li><li><a>SQL</a></li><li><a>Apache Spark</a></li>
  </ul></div>
</body></html>
"""

parser = JobDetailParser(detail_html, url1, "CNTT - Phần mềm")
record = parser.parse()

assert record["job_id"]      == "35C541AE",        f"job_id: {record['job_id']}"
assert record["title"]       == "Senior Data Engineer", f"title: {record['title']}"
assert record["company_name"]== "TechCorp VN",     f"company: {record['company_name']}"
assert record["salary_raw"]  != "",                f"salary empty"
assert record["deadline_date"]!= "",               f"deadline empty"
assert "Python" in record["tags"],                 f"tags: {record['tags']}"
assert len(record["job_description_raw"]) > 0,    f"desc empty"
assert len(record["job_requirements_raw"]) > 0,   f"req empty"
assert len(record["benefits_raw"]) > 0,           f"benefits empty"
assert record["crawled_category"] == "CNTT - Phần mềm"

print(f"✓ JobDetailParser")
print(f"  title       : {record['title']}")
print(f"  company     : {record['company_name']}")
print(f"  salary_raw  : {record['salary_raw']}")
print(f"  deadline    : {record['deadline_date']}")
print(f"  tags        : {record['tags']}")
print(f"  desc items  : {len(record['job_description_raw'])}")
print(f"  req  items  : {len(record['job_requirements_raw'])}")
print(f"  benefit items: {len(record['benefits_raw'])}")

# ── Test 5: Deduplicator ────────────────────────────────────
dedup = Deduplicator()
assert not dedup.is_duplicate(record)
dedup.mark_seen(record)
assert dedup.is_duplicate(record)

record2 = dict(record)
record2["job_id"] = "NEWJOB99"
assert not dedup.is_duplicate(record2)
print("✓ Deduplicator")

print()
print("=" * 40)
print("  TẤT CẢ TESTS PASSED ✅")
print("=" * 40)
