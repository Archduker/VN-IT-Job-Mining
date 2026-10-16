---
name: data-integration-miner
description: >-
  Chuyên gia điều phối quy trình Data Mining hiện đại và tích hợp dữ liệu đa nguồn (Data Integration & Harmonization).
  Chuyên sâu về: ánh xạ schema dị cấu trúc từ 7 sàn tuyển dụng về Common Target Schema,
  khử trùng lặp ngữ nghĩa xuyên sàn (Cross-Platform Entity Resolution via Embeddings),
  và tích hợp các mô hình AI/ML hiện đại: LLM Few-shot trích xuất kỹ năng ngầm định (SD3),
  NLP Zero-Shot phân loại Job Family (SD2), Isolation Forest phát hiện tin rác, và khai phá luật kết hợp kỹ năng (FP-Growth).
---

# Data Integration Miner Skill

Kỹ năng này trang bị cho AI Agent năng lực điều phối toàn bộ chuỗi giá trị từ dữ liệu thô đa nguồn sang Bộ dữ liệu Vàng (Golden Master Dataset), làm tiền đề giải quyết 5 mục tiêu chiến lược SD1 — SD5.

---

## 1. Quy Trình Ánh Xạ Schema Đa Nguồn (Schema Harmonization)

Khi tích hợp dữ liệu từ 7 website tuyển dụng, Agent đối chiếu và ánh xạ theo bảng từ điển dữ liệu (Data Dictionary):

### Bảng Ánh Xạ Chuẩn Sang Common Target Schema:

| Trường Đích (Common Target) | Kiểu | TopCV | TopDev | VietnamWorks | ITViec | CareerViet | Vieclam24h | Glints |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `job_id_global` | `str` | `topcv_{id}` | `topdev_{id}` | `vnw_{id}` | `itviec_{id}` | `careerviet_{id}` | `24h_{id}` | `glints_{id}` |
| `job_title` | `str` | `box-header-job__title` | `title` | `jobTitle` | `title` | `title` | `title` | `title` |
| `salary_min_vnd` | `float` | Parse từ header salary | `salary.min` (convert USD) | `salaryMin` | Parse salary range | `salary` min | `salary` min | `salary.min` |
| `salary_max_vnd` | `float` | Parse từ header salary | `salary.max` (convert USD) | `salaryMax` | Parse salary range | `salary` max | `salary` max | `salary.max` |
| `min_experience_years`| `float` | `box--experience` | `experience` | `yearsOfExperience` | Parse JD | `experience` | `experience` | `experience` |
| `work_location_city` | `str` | `box--location` | `addresses[0]` | `workingLocations` | `location` | `location` | `location` | `location` |
| `company_name` | `str` | `company-name` | `company.name`| `companyName` | `company` | `company` | `company` | `company.name` |
| `raw_skill_tags` | `list` | `badge-tag-list` | `skills` | `skills` | `skills` | `tags` | `tags` | `skills` |
| `job_description_raw`| `str` | `requirements_html`| `description` | `jobDescription` | `description` | `job-desc` | `description` | `description` |

---

## 2. Ứng Dụng AI: Trích Xuất & Chuẩn Hóa Kỹ Năng (SD3)

### 2.1. Trích xuất kỹ năng ngầm định bằng LLM (Prompt Template)
Agent sử dụng prompt chuyên biệt để hướng dẫn mô hình ngôn ngữ lớn bóc tách kỹ năng từ văn bản tự do:

```markdown
Bạn là chuyên gia phân tích thị trường lao động IT. Hãy trích xuất danh sách kỹ năng nghề nghiệp từ văn bản tuyển dụng sau.
Phân chia thành 3 nhóm rõ ràng:
1. hard_skills: Tên ngôn ngữ lập trình, framework, cơ sở dữ liệu, công cụ cloud, kiến trúc hệ thống cụ thể.
2. domain_knowledge: Nghiệp vụ chuyên ngành (Fintech, E-commerce, Healthcare, Embedded, AI/ML, Blockchain).
3. methodologies_soft_skills: Phương pháp luận và kỹ năng mềm (Agile/Scrum, CI/CD mindset, Teamwork, Problem-solving).

[VĂN BẢN TUYỂN DỤNG]
{job_description_clean}

Trả về DUY NHẤT định dạng JSON:
{
  "hard_skills": ["Python", "Docker", "Redis"],
  "domain_knowledge": ["Payment Gateway"],
  "methodologies_soft_skills": ["Scrum", "CI/CD"]
}
```

### 2.2. Chuẩn hóa tên kỹ năng về Từ điển Chuẩn (Skill Normalization)
Sử dụng Sentence-Transformers tính cosine similarity với từ điển kỹ năng chuẩn (ESCO IT Skills):
```python
from sentence_transformers import SentenceTransformer, util

model = SentenceTransformer("all-MiniLM-L6-v2")

def normalize_skill(extracted_skill: str, standard_skills: list, threshold=0.88) -> str:
    skill_emb = model.encode(extracted_skill, convert_to_tensor=True)
    std_embs = model.encode(standard_skills, convert_to_tensor=True)
    
    hits = util.semantic_search(skill_emb, std_embs, top_k=1)
    best_score = hits[0][0]["score"]
    best_idx = hits[0][0]["corpus_id"]
    
    if best_score >= threshold:
        return standard_skills[best_idx]
    return extracted_skill  # Giữ nguyên nếu là kỹ năng mới nổi (Emerging Skill)
```

---

## 3. Ứng Dụng NLP: Phân Loại 12 Job Family Chuẩn (SD2)

Định nghĩa 12 nhóm nghề nghiệp chuẩn của ngành IT Việt Nam:
1. `Backend Development`
2. `Frontend Development`
3. `Fullstack Development`
4. `Mobile Development (iOS / Android / Flutter / RN)`
5. `DevOps / Cloud / SRE / System Engineer`
6. `Data Engineering & Big Data`
7. `Data Science / AI / Machine Learning`
8. `Software QA / QC / Automation Test`
9. `Cyber Security / Information Security`
10. `Product Management / Business Analyst (BA)`
11. `UI/UX Design`
12. `Embedded System / IoT / Hardware`

Agent áp dụng Zero-shot Classification để phân loại bài đăng tuyển dụng dựa trên tiêu đề và phần tóm tắt JD.

---

## 4. Khử Trùng Lặp Ngữ Nghĩa Xuyên Sàn (Cross-Platform Entity Resolution)

Thuật toán 3 bước phát hiện tin đăng chéo trên nhiều sàn:
1. **Blocking:** Nhóm các tin có cùng Công ty và cùng Thành phố.
2. **Text Similarity:** Tính khoảng cách Levenshtein trên Tiêu đề và Cosine Similarity trên TF-IDF / Embedding của văn bản JD.
3. **Decision Rule:**
   - Nếu $\text{Sim}(\text{Title}) > 0.85$ VÀ $\text{Sim}(\text{JD}) > 0.90$ VÀ chênh lệch ngày đăng $< 14$ ngày:
     $\rightarrow$ Gộp thành 1 thực thể việc làm duy nhất (Master Record), lưu vết `sources: ["topcv", "itviec"]`.
