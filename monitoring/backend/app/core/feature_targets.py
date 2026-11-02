# -*- coding: utf-8 -*-
"""Cấu hình 8 feature target và vị trí của chúng trong raw_payload từng nguồn.

Vị trí trường thô bám theo các hàm _flatten_<source> trong
preprocessing/integration/json_flattener.py. Sửa flattener thì sửa cả bảng này.
Mỗi vị trí là một đường dẫn trong raw_payload; phần tử cuối dạng "re:<pattern>"
chọn các dòng khớp trong một list (như detail-box của CareerViet).
"""

from typing import Dict, List, Tuple

Path = Tuple[str, ...]

FEATURES: List[Dict[str, object]] = [
    {
        "code": "F1", "name": "Title → nhóm nghề", "use": "Phân cụm, phân loại nghề",
        "std": "job_title_clean, job_family (nhóm nghề)", "fields": ["job_title"],
        "how": "Bỏ mã tuyển dụng, chuẩn hóa khoảng trắng; xếp nhóm nghề bằng từ khóa.",
        "problem": "Title dính mã tuyển dụng hoặc ký tự thừa, một phần không xếp được vào nhóm nghề",
        "where": "Normalizer", "fix": "Bổ sung từ khóa nhóm nghề, loại mã trong ngoặc",
    },
    {
        "code": "F2", "name": "Company", "use": "Khử trùng lặp liên nguồn",
        "std": "Khóa so khớp (viết thường, bỏ TNHH/CP/JSC)", "fields": ["company_name"],
        "how": "Bỏ hậu tố pháp lý, viết thường để làm khóa so khớp.",
        "problem": "Cùng một công ty có nhiều cách viết nên khó khớp giữa các nguồn",
        "where": "Luật chuẩn hóa", "fix": "Bỏ hậu tố pháp lý rồi so khớp gần đúng",
    },
    {
        "code": "F3", "name": "Location", "use": "Phân tích theo địa phương",
        "std": "primary_city (tỉnh/thành chuẩn)", "fields": ["raw_location_text"],
        "how": "Tách tỉnh/thành khỏi địa chỉ, gom alias (HCM, TP.HCM, Sài Gòn…).",
        "problem": "Địa chỉ dài, một chuỗi có nhiều địa điểm, nhiều cách viết cùng một tỉnh",
        "where": "Luật chuẩn hóa", "fix": "Mở rộng bảng alias địa danh",
    },
    {
        "code": "F4", "name": "Salary", "use": "Mô hình dự đoán lương",
        "std": "salary_min_vnd, salary_max_vnd", "fields": ["raw_salary_text"],
        "how": "Parse cascade: regex header rồi quét JD; USD đổi sang VND; thỏa thuận giữ NaN kèm cờ.",
        "problem": "Chuỗi lương nhiều kiểu: khoảng, up to, USD/VND, thỏa thuận",
        "where": "Normalizer", "fix": "Giữ cờ thỏa thuận, đánh dấu ngoại lai thay vì xóa",
    },
    {
        "code": "F5", "name": "Experience", "use": "Đặc trưng cho mô hình lương",
        "std": "Số năm kinh nghiệm tối thiểu", "fields": ["raw_experience_text"],
        "how": "Lấy số năm đầu tiên trong chuỗi; không yêu cầu kinh nghiệm → 0.",
        "problem": "Kinh nghiệm ở dạng chữ, chưa có bộ parse số năm trong pipeline",
        "where": "Normalizer", "fix": "Thêm regex số năm vào bước Transformation",
    },
    {
        "code": "F6", "name": "Level", "use": "Phân tích theo cấp bậc",
        "std": "job_seniority (6 bậc)", "fields": ["raw_seniority_text"],
        "how": "Ánh xạ nhãn của nguồn về thang chuẩn; thiếu thì suy từ title.",
        "problem": "Nhãn cấp bậc chung chung, không khớp thang chuẩn hoặc mâu thuẫn với title",
        "where": "Luật chuẩn hóa", "fix": "Bảng alias riêng theo nguồn, ưu tiên title khi mâu thuẫn",
    },
    {
        "code": "F7", "name": "Skills", "use": "Luật kết hợp, phân cụm kỹ năng",
        "std": "skills_list (từ điển kỹ năng)", "fields": ["skills_list"],
        "how": "Lấy danh sách kỹ năng của nguồn; chưa quét từ điển trong mô tả.",
        "problem": "Danh sách kỹ năng chưa đối chiếu từ điển chuẩn, còn lẫn biến thể tên",
        "where": "Luật chuẩn hóa", "fix": "Gom alias kỹ năng về từ điển chuẩn",
    },
    {
        "code": "F8", "name": "Posted / deadline", "use": "Phân tích theo tuần, độ tươi tin",
        "std": "raw_posted_date, raw_deadline", "fields": ["raw_posted_date", "raw_deadline"],
        "how": "Giữ chuỗi ngày gốc; bước Transformation sẽ đưa về ISO.",
        "problem": "Ngày nhiều định dạng, có nguồn dùng ngày cập nhật thay ngày đăng",
        "where": "Normalizer", "fix": "Parse về ngày ISO, kiểm tra hạn nộp sau ngày đăng",
    },
]

RAW_PATHS: Dict[str, Dict[str, List[Path]]] = {
    "careerviet": {
        "F1": [("title",)],
        "F2": [("job-company-name",)],
        "F3": [("map",), ("detail-row", "Địa điểm làm việc")],
        "F4": [("detail-box", "re:^Lương")],
        "F5": [("detail-box", "re:^Kinh nghiệm")],
        "F6": [("detail-box", "re:^Cấp bậc")],
        "F7": [("detail-row", "Yêu Cầu Công Việc")],
        "F8": [("detail-box", "re:^(Ngày cập nhật|Hết hạn)")],
    },
    "glints": {
        "F1": [("job-title",), ("title",), ("job_posting_jsonld", "title")],
        "F2": [("company-name",), ("company",)],
        "F3": [("job_posting_jsonld", "jobLocation")],
        "F4": [("salary",)],
        "F5": [("requirements",)],
        "F6": [],
        "F7": [("skills",)],
        "F8": [("job_posting_jsonld", "datePosted"), ("job_posting_jsonld", "validThrough")],
    },
    "itviec": {
        "F1": [("title",)],
        "F2": [("company_name",), ("company",)],
        "F3": [("work_location",)],
        "F4": [("salary_display_text",), ("job_posting_jsonld", "baseSalary")],
        "F5": [("job_posting_jsonld", "experienceRequirements")],
        "F6": [],
        "F7": [("skill_tags",), ("skills",)],
        "F8": [("posted_at_raw",), ("job_posting_jsonld", "validThrough")],
    },
    "jobsgo": {
        "F1": [("title",)],
        "F2": [("company",)],
        "F3": [("location",), ("working_places",)],
        "F4": [("salary_raw",)],
        "F5": [("experience",)],
        "F6": [("general_info", "job_level")],
        "F7": [("requirements_bullets",)],
        "F8": [("general_info", "posted_date"), ("deadline_raw",)],
    },
    "topcv": {
        "F1": [("title",)],
        "F2": [("company",)],
        "F3": [("location",), ("working_places",)],
        "F4": [("salary_raw",)],
        "F5": [("experience",)],
        "F6": [("general_info", "Cấp bậc")],
        "F7": [("overview_tags", "Chuyên môn"), ("required_skills",), ("industry_knowledge",)],
        "F8": [("deadline_raw",)],
    },
    "topdev": {
        "F1": [("title",), ("job-title",)],
        "F2": [("company", "company_name"), ("company", "name"), ("company",)],
        "F3": [("addresses", "address_region_list")],
        "F4": [("salary_raw",), ("salary",)],
        "F5": [("experience",), ("extra", "experience"), ("experiences_str",)],
        "F6": [("seniority_text",), ("job_level",), ("job_levels_str",)],
        "F7": [("skills_arr",), ("skills_str",)],
        "F8": [("recalled_at",), ("created_at",)],
    },
    "vieclam24h": {
        "F1": [("title",)],
        "F2": [("company",)],
        "F3": [("location_summary",)],
        "F4": [("salary",)],
        "F5": [("experience_summary",)],
        "F6": [("general_info", "level")],
        "F7": [("keywords",)],
        "F8": [("general_info", "posted_date"), ("deadline",)],
    },
    "vietnamworks": {
        "F1": [("jobTitle",), ("title",)],
        "F2": [("companyName",)],
        "F3": [("location",), ("workingLocations",)],
        "F4": [("salaryMin",), ("salaryMax",), ("prettySalary",)],
        "F5": [("yearsOfExperience",)],
        "F6": [("jobLevelVI",), ("jobLevel",)],
        "F7": [("skills",)],
        "F8": [("createdOn",), ("approvedOn",), ("expiredOn",)],
    },
}

SOURCE_DOMAINS: Dict[str, str] = {
    "careerviet": "careerviet.vn", "glints": "glints.com", "itviec": "itviec.com",
    "jobsgo": "jobsgo.vn", "topcv": "topcv.vn", "topdev": "topdev.vn",
    "vieclam24h": "vieclam24h.vn", "vietnamworks": "vietnamworks.com",
}

# Feature mà Integration cố ý để trống, bước GenAI imputer sẽ bù từ JD.
FILLED_BY_IMPUTER = {("careerviet", "F7"), ("jobsgo", "F7")}

# Vấn đề đã kiểm chứng riêng cho từng nguồn; ghi đè nội dung mặc định của feature.
SOURCE_ISSUES: Dict[str, Dict[str, Dict[str, str]]] = {
    "careerviet": {
        "F4": {"problem": "Thông tin gói trong detail-box, các dòng bị lặp, nhãn dính vào giá trị (\"Lương Lương:\")",
               "where": "Scraper", "fix": "Khử dòng trùng trong detail-box, cắt nhãn trước khi parse"},
        "F6": {"problem": "Cấp bậc \"Nhân viên\" không khớp thang chuẩn và có thể mâu thuẫn với title",
               "where": "Luật chuẩn hóa", "fix": "Ưu tiên cấp bậc suy từ title"},
        "F7": {"problem": "Trang không có ô kỹ năng; job-tags là tag SEO nên không dùng",
               "where": "Normalizer", "fix": "Imputer quét kỹ năng từ phần yêu cầu công việc"},
    },
    "itviec": {
        "F6": {"problem": "Trang không có ô cấp bậc riêng", "where": "Luật chuẩn hóa",
               "fix": "Suy cấp bậc từ title"},
    },
    "jobsgo": {
        "F7": {"problem": "Trang không có ô kỹ năng; occupations là ngành nghề nên không dùng",
               "where": "Normalizer", "fix": "Imputer quét kỹ năng từ phần yêu cầu công việc"},
    },
    "vietnamworks": {
        "F4": {"problem": "salaryMin/salaryMax bằng 0 khi lương ẩn, lúc đó chỉ còn prettySalary",
               "where": "Normalizer", "fix": "Coi 0 là thiếu, dùng prettySalary làm dự phòng"},
    },
}
