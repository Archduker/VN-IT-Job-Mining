# -*- coding: utf-8 -*-
"""crawlers.preprocessing.eda.loader
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Bộ nạp dữ liệu an toàn cho Hệ thống EDA (VN-IT-Job-Mining).

Chức năng:
- Kiểm tra tính toàn vẹn cú pháp JSON và cấu trúc mảng bản ghi.
- Nạp an toàn dữ liệu từ tệp JSON (UTF-8, xử lý BOM).
- Chuyển đổi danh sách bản ghi thành Pandas DataFrame phẳng hóa cấu trúc lồng.
- Bảo toàn nguyên vẹn dữ liệu gốc, không chỉnh sửa hay ghi đè.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union

import pandas as pd


class EDALoaderError(Exception):
    """Lớp ngoại lệ cơ sở cho các lỗi nạp dữ liệu trong EDA."""
    pass


class InvalidJSONStructureError(EDALoaderError):
    """Ngoại lệ khi cấu trúc JSON không phải là mảng các đối tượng (JSON Array of Objects)."""
    pass


class EDALoader:
    """Bộ nạp và tiền xử lý cấu trúc dữ liệu phục vụ phân tích EDA."""

    last_load_report: Optional[Dict[str, Any]] = None

    @classmethod
    def load_raw_records_with_report(
        cls, file_path: Union[str, Path]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Đọc an toàn mảng JSON bản ghi từ tệp đĩa kèm báo cáo chất lượng phần tử.

        Bảo toàn thứ tự gốc của các phần tử. Nếu gặp phần tử không phải dict (ví dụ null, số, chuỗi),
        phần tử đó được ghi nhận chi tiết (vị trí index, kiểu dữ liệu, preview tối đa 100 ký tự)
        và không đưa vào danh sách valid_records để tránh làm crash các bộ phân tích phía sau.

        Args:
            file_path: Đường dẫn tới tệp JSON đầu vào.

        Returns:
            Tuple gồm:
            - valid_records: Danh sách các dict bản ghi hợp lệ.
            - report: Dict chứa các chỉ số cấp tệp (total_raw_elements, valid_record_count,
              invalid_element_count, invalid_elements).

        Raises:
            FileNotFoundError: Nếu tệp không tồn tại.
            EDALoaderError: Nếu tệp rỗng (0 bytes).
            json.JSONDecodeError: Nếu cú pháp JSON không hợp lệ.
            InvalidJSONStructureError: Nếu nội dung JSON không phải dạng list.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Tệp dữ liệu không tồn tại: {path}")

        if path.stat().st_size == 0:
            raise EDALoaderError(f"Tệp dữ liệu rỗng (0 bytes): {path}")

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise EDALoaderError(f"Tệp không có nội dung văn bản: {path}")
                data = json.loads(content)
        except json.JSONDecodeError as err:
            raise json.JSONDecodeError(
                f"Lỗi cú pháp JSON trong tệp {path}: {err.msg}",
                err.doc,
                err.pos,
            ) from err

        if not isinstance(data, list):
            raise InvalidJSONStructureError(
                f"Dữ liệu mong đợi dạng mảng (JSON array/list), nhưng nhận được: {type(data).__name__}"
            )

        valid_records: List[Dict[str, Any]] = []
        invalid_elements: List[Dict[str, Any]] = []

        for idx, item in enumerate(data):
            if isinstance(item, dict):
                valid_records.append(item)
            else:
                raw_preview = str(item)
                if len(raw_preview) > 100:
                    raw_preview = raw_preview[:97] + "..."
                invalid_elements.append({
                    "index": idx,
                    "element_type": type(item).__name__,
                    "raw_preview": raw_preview,
                })

        report: Dict[str, Any] = {
            "file_path": str(path),
            "file_size_bytes": path.stat().st_size,
            "total_raw_elements": len(data),
            "valid_record_count": len(valid_records),
            "invalid_element_count": len(invalid_elements),
            "invalid_elements": invalid_elements,
        }
        cls.last_load_report = report
        return valid_records, report

    @classmethod
    def load_raw_records(cls, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Đọc an toàn mảng JSON bản ghi từ tệp đĩa, trả về danh sách các dict hợp lệ.

        Duy trì khả năng tương thích ngược hoàn toàn với các lời gọi hiện có.
        """
        valid_records, _ = cls.load_raw_records_with_report(file_path)
        return valid_records


    @staticmethod
    def stream_records(file_path: Union[str, Path]) -> Generator[Dict[str, Any], None, None]:
        """Duyệt tuần tự từng bản ghi từ mảng JSON (phục vụ xử lý tiết kiệm RAM).

        Args:
            file_path: Đường dẫn tới tệp JSON đầu vào.

        Yields:
            Dict đại diện cho từng bài tuyển dụng.
        """
        records = EDALoader.load_raw_records(file_path)
        for idx, item in enumerate(records):
            if isinstance(item, dict):
                yield item

    @staticmethod
    def records_to_dataframe(records: List[Dict[str, Any]]) -> pd.DataFrame:
        """Chuyển đổi danh sách bản ghi thành Pandas DataFrame phẳng hóa cấu trúc lồng.

        Trích xuất các cột chính:
        - _meta.* (unified_id, source, source_job_id, url, crawled_at, language)
        - title, company
        - salary.* (salary_min, salary_max, salary_currency, salary_type, is_negotiable, has_commission, salary_raw_text)
        - description_list, requirements_list, benefits_list
        - tags.skills, tags.requirements, tags.benefits
        - locations, location_text, employment_type_text, seniority_text, posted_date_text, deadline_text
        - extra

        Args:
            records: Danh sách dict bản ghi.

        Returns:
            DataFrame phẳng với kiểu dữ liệu chuẩn hóa an toàn.
        """
        if not records:
            return pd.DataFrame()

        rows: List[Dict[str, Any]] = []
        for rec in records:
            if not isinstance(rec, dict):
                continue

            meta = rec.get("_meta") if isinstance(rec.get("_meta"), dict) else {}
            salary = rec.get("salary") if isinstance(rec.get("salary"), dict) else {}
            tags = rec.get("tags") if isinstance(rec.get("tags"), dict) else {}
            extra = rec.get("extra") if isinstance(rec.get("extra"), dict) else {}

            row: Dict[str, Any] = {
                # Khối _meta
                "unified_id": meta.get("unified_id"),
                "source": meta.get("source"),
                "source_job_id": meta.get("source_job_id"),
                "url": meta.get("url"),
                "crawled_at": meta.get("crawled_at"),
                "language": meta.get("language"),

                # Thông tin cơ bản
                "title": rec.get("title"),
                "company": rec.get("company"),

                # Khối salary
                "salary_min": salary.get("salary_min"),
                "salary_max": salary.get("salary_max"),
                "salary_currency": salary.get("salary_currency"),
                "salary_type": salary.get("salary_type"),
                "is_negotiable": salary.get("is_negotiable"),
                "has_commission": salary.get("has_commission"),
                "salary_raw_text": salary.get("salary_raw_text"),

                # Danh sách văn bản
                "description_list": rec.get("description_list"),
                "requirements_list": rec.get("requirements_list"),
                "benefits_list": rec.get("benefits_list"),

                # Khối tags
                "skills": tags.get("skills"),
                "tag_requirements": tags.get("requirements"),
                "tag_benefits": tags.get("benefits"),

                # Thuộc tính công việc & Mốc thời gian
                "locations": rec.get("locations"),
                "location_text": rec.get("location_text"),
                "employment_type_text": rec.get("employment_type_text"),
                "seniority_text": rec.get("seniority_text"),
                "posted_date_text": rec.get("posted_date_text"),
                "deadline_text": rec.get("deadline_text"),

                # Trường riêng
                "extra": extra,
            }
            rows.append(row)

        df = pd.DataFrame(rows)

        # Chuyển đổi an toàn kiểu số cho lương
        if "salary_min" in df.columns:
            df["salary_min"] = pd.to_numeric(df["salary_min"], errors="coerce")
        if "salary_max" in df.columns:
            df["salary_max"] = pd.to_numeric(df["salary_max"], errors="coerce")

        return df

    @classmethod
    def load_dataframe(cls, file_path: Union[str, Path]) -> pd.DataFrame:
        """Hàm tiện ích nạp tệp và chuyển đổi thành DataFrame trong 1 lệnh duy nhất.

        Args:
            file_path: Đường dẫn tới tệp JSON.

        Returns:
            DataFrame đã phẳng hóa.
        """
        records = cls.load_raw_records(file_path)
        return cls.records_to_dataframe(records)


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    default_path = Path("data/processed/preClean/merged_jobs_clean.json")
    target_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    print(f"[*] Đang nạp và kiểm tra tệp: {target_path} ...")
    recs = EDALoader.load_raw_records(target_path)
    print(f"[+] Nạp thành công {len(recs):,} bản ghi thô dạng JSON Array.")
    df = EDALoader.records_to_dataframe(recs)
    print(f"[+] Đã phẳng hóa thành DataFrame: shape={df.shape}, memory={df.memory_usage().sum() / (1024*1024):.2f} MB")
    print("\nThông tin các cột trong DataFrame:")
    print(df.info(verbose=False))
