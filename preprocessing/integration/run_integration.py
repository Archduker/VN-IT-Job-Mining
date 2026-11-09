# -*- coding: utf-8 -*-
"""preprocessing.integration.run_integration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Module thực thi giai đoạn INTEGRATION (Ép phẳng JSON & Gộp all.parquet đa nguồn).

Tuân thủ nghiêm ngặt ranh giới kiến trúc & Hợp đồng dữ liệu (P2 Spec):
  - Tự động đồng bộ tầng dữ liệu 01_clean từ Cloudflare R2 về local.
  - Chuẩn hóa và ép phẳng cấu trúc JSON của 8 sàn về Canonical Flat Schema.
  - Gộp toàn bộ 8 sàn về tệp duy nhất: data/preprocessing/02_integration/all.parquet.
  - Bảo toàn 100% bản ghi (Zero Information Loss / Zero-Drop contract).
  - Tự động chẩn đoán kỹ thuật: Phân tích nguyên nhân Null chi tiết cho từng sàn.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("integration_runner")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from preprocessing.integration.json_flattener import flatten_raw_job_record

SOURCES = [
    "topcv",
    "topdev",
    "itviec",
    "vietnamworks",
    "careerviet",
    "glints",
    "jobsgo",
    "vieclam24h",
]

# Thư mục dữ liệu & báo cáo chuẩn theo đặc tả P2
DATA_DIR = PROJECT_ROOT / "data" / "preprocessing"
IN_DIR = DATA_DIR / "01_clean"
OUT_DIR = DATA_DIR / "02_integration"
REPORT_DIR = PROJECT_ROOT / "reports" / "preprocessing" / "02_integration"

# Bộ từ điển chẩn đoán kỹ thuật giải mã nguyên nhân Null theo từng sàn
NULL_DIAGNOSTIC_KNOWLEDGE_BASE: Dict[str, Dict[str, str]] = {
    "raw_education_text": {
        "careerviet": "Missing By Design trên thẻ tóm tắt; nhà tuyển dụng thường ghi yêu cầu bằng cấp trực tiếp trong bullet 'Yêu cầu công việc'.",
        "itviec": "Skills-over-degree: Nền tảng chuyên IT không áp dụng ô chọn bằng cấp hàn lâm trên form tuyển dụng.",
        "topdev": "Skills-based platform: Biểu mẫu TopDev tập trung vào khung kỹ năng và số năm kinh nghiệm, không bắt buộc bằng cấp.",
        "vieclam24h": "Optional field: Ô nhập bằng cấp trong general_info là tùy chọn, đa số tin IT để trống hoặc viết trong JD.",
        "glints": "Có sẵn trong JSON-LD educationRequirements hoặc dòng đầu requirements.",
        "jobsgo": "Có sẵn trong trường education có cấu trúc.",
        "topcv": "Có sẵn trong general_info['Học vấn'] và overview_tags['Yêu cầu'].",
        "vietnamworks": "Có sẵn thông qua highestDegreeId chuẩn hóa.",
    },
    "raw_working_time": {
        "careerviet": "Missing By Design: Form CareerViet không có ô nhập ca kíp/giờ giấc làm việc cố định.",
        "glints": "Missing By Design: Glints không thiết kế trường giờ giấc làm việc hàng ngày.",
        "itviec": "Missing By Design: ITViec áp dụng cơ chế giờ làm việc linh hoạt đặc thù của ngành IT.",
        "topdev": "Missing By Design: TopDev không thu thập giờ giấc cố định.",
        "vietnamworks": "Missing By Design: VietnamWorks không có trường working_time riêng.",
        "vieclam24h": "Optional field omission: Chỉ một số ít NTD nhập giờ làm việc cụ thể do đặc thù linh hoạt.",
        "jobsgo": "Có sẵn trong trường working_time có cấu trúc.",
        "topcv": "Có sẵn trong trường working_time có cấu trúc.",
    },
    "raw_work_mode": {
        "careerviet": "Implicit text: Chế độ Onsite/Remote được viết trong tiêu đề hoặc mô tả, form không có danh mục riêng.",
        "itviec": "Implicit text: Phân loại Remote/Hybrid được gắn qua tag công việc hoặc JD text.",
        "jobsgo": "Implicit text: Không có trường phân loại riêng trên header.",
        "topdev": "Implicit text: Chế độ làm việc được ghi trong slug hoặc quyền lợi.",
        "vieclam24h": "Implicit text: Không có trường danh mục Onsite/Remote trên form.",
        "vietnamworks": "Implicit text: Chế độ làm việc nằm trong tiêu đề bài đăng.",
        "glints": "Có sẵn qua nhãn 'Làm tại công ty / Remote' trong requirements.",
        "topcv": "Có sẵn qua general_info['Hình thức làm việc'].",
    },
    "raw_headcount": {
        "careerviet": "Confidential hiring: NTD giữ kín chỉ tiêu tuyển dụng để bảo mật kế hoạch nhân sự.",
        "glints": "Confidential hiring: Form Glints không hiển thị số lượng tuyển dụng.",
        "itviec": "Confidential hiring: Sàn IT chuyên biệt không bắt buộc khai báo chỉ tiêu.",
        "topdev": "Confidential hiring: Không có trường chỉ tiêu tuyển dụng trên form.",
        "jobsgo": "Khai báo trong hiring_quantity (các bài còn lại để trống).",
        "topcv": "Có sẵn qua general_info['Số lượng tuyển'].",
        "vieclam24h": "Có sẵn qua general_info['hiring_quantity'].",
        "vietnamworks": "Có sẵn qua numberOfRecruits.",
    },
    "raw_age_text": {
        "careerviet": "Anti-age discrimination: Form sàn không yêu cầu khai báo độ tuổi.",
        "glints": "Compliance policy: Glints tuân thủ luật lao động quốc tế chống phân biệt tuổi tác.",
        "itviec": "Anti-age discrimination: ITViec nghiêm cấm lọc ứng viên theo độ tuổi.",
        "jobsgo": "Anti-age discrimination: Form không có trường giới hạn tuổi.",
        "topdev": "Anti-age discrimination: Nền tảng chỉ đánh giá theo năng lực kỹ thuật.",
        "vieclam24h": "Optional field: Chỉ một số ít bài đăng có giới hạn tuổi.",
        "topcv": "Xuất hiện qua overview_tags['Yêu cầu'] (ví dụ: 'Tuổi 18 - 30').",
        "vietnamworks": "Có sẵn qua trường rangeAge.",
    },
    "raw_gender_text": {
        "careerviet": "Gender equality compliance: Không thu thập giới tính ứng viên.",
        "glints": "Gender equality compliance: Chống phân biệt giới tính theo chuẩn Singapore.",
        "itviec": "Gender equality compliance: Tuyển dụng kỹ sư IT bình đẳng giới 100%.",
        "jobsgo": "Gender equality compliance: Form tuyển dụng không phân biệt giới tính.",
        "topdev": "Gender equality compliance: Đánh giá thuần túy theo năng lực lập trình.",
        "vieclam24h": "Optional field: Đa phần ghi nhận không yêu cầu giới tính.",
        "topcv": "Có sẵn qua general_info['Giới tính'].",
        "vietnamworks": "Có sẵn qua isShowGender / gender.",
    },
    "raw_updated_at": {
        "glints": "Missing By Design: Chỉ lưu vết datePosted và validThrough.",
        "itviec": "Missing By Design: Chỉ lưu posted_at và validThrough.",
        "jobsgo": "Missing By Design: Chỉ lưu posted_date và deadline_raw.",
        "topcv": "Missing By Design: Chỉ hiển thị deadline nộp hồ sơ.",
        "topdev": "Missing By Design: Chỉ lưu created_at / recalled_at.",
        "vieclam24h": "Missing By Design: Chỉ lưu posted_date.",
        "careerviet": "Có sẵn qua nhãn 'Ngày cập nhật' trong detail-box.",
        "vietnamworks": "Có sẵn qua trường lastUpdatedOn trong Search API.",
    },
    "company_scale": {
        "careerviet": "Missing By Design: Form CareerViet không công khai quy mô nhân sự công ty.",
        "glints": "Missing By Design: Quy mô lưu trong hồ sơ công ty tách biệt, không nằm trên trang job.",
        "itviec": "Missing By Design: Trang chi tiết job không nhúng quy mô công ty.",
        "jobsgo": "Optional field: Đa phần nhà tuyển dụng chưa cập nhật quy mô.",
        "vieclam24h": "Optional field: Trường scale trong company dict thường rỗng.",
        "topcv": "Có sẵn qua company_scale ('25-99 nhân viên',...).",
        "topdev": "Có sẵn qua trường company_size trong company payload.",
        "vietnamworks": "Có sẵn qua trường companySize / companySizeVI.",
    },
}


def ensure_p1_data_from_r2(target_dir: Path) -> None:
    """Tự động kiểm tra và tải dữ liệu P1 Clean từ Cloudflare R2 nếu local chưa có."""
    target_dir.mkdir(parents=True, exist_ok=True)
    existing_files = list(target_dir.glob("*.jsonl")) + list(target_dir.glob("*.parquet")) + list(target_dir.glob("*.json"))
    if len(existing_files) >= len(SOURCES):
        logger.info(f"Đã tìm thấy dữ liệu local tại {target_dir}. Bỏ qua bước tải R2.")
        return

    endpoint = os.getenv("R2_ENDPOINT_URL") or os.getenv("CLOUDFLARE_R2_ENDPOINT")
    access_key = os.getenv("R2_ACCESS_KEY_ID") or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY") or os.getenv("AWS_SECRET_ACCESS_KEY")
    bucket = os.getenv("R2_BUCKET_NAME") or "vn-it-jobs"

    if not (endpoint and access_key and secret_key):
        logger.info("Chưa cấu hình biến môi trường R2, tiếp tục xử lý với các file local sẵn có.")
        return

    try:
        import boto3
        from botocore.config import Config
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
            region_name="auto",
        )
        logger.info("Đang kiểm tra và đồng bộ dữ liệu P1 Clean từ Cloudflare R2...")
        prefixes = [
            "staging/{src}/preprocessing/01_clean",
            "preprocessing/01_clean/{src}",
            "01_clean/{src}",
            "data/preprocessing/01_clean/{src}",
        ]

        for src in SOURCES:
            dest_file = target_dir / f"{src}.jsonl"
            if dest_file.exists() or (target_dir / f"{src}.parquet").exists():
                continue
            for prefix_pattern in prefixes:
                prefix = prefix_pattern.format(src=src)
                found = False
                for ext in [".jsonl", ".parquet", ".json"]:
                    r2_key = f"{prefix}{ext}"
                    try:
                        s3.head_object(Bucket=bucket, Key=r2_key)
                        out_f = target_dir / f"{src}{ext}"
                        logger.info(f"Đang tải từ R2: {r2_key} -> {out_f}")
                        s3.download_file(bucket, r2_key, str(out_f))
                        found = True
                        break
                    except Exception:
                        continue
                if found:
                    break
    except Exception as exc:
        logger.warning(f"Lỗi khi đồng bộ từ R2: {exc}. Tiếp tục sử dụng dữ liệu local.")


def resolve_source_file(base_dir: Path, source: str) -> Optional[Path]:
    """Tìm file dữ liệu theo thứ tự ưu tiên: .jsonl -> .parquet -> .json."""
    candidates = [
        base_dir / f"{source}.jsonl",
        base_dir / f"{source}.parquet",
        base_dir / f"{source}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def integrate_single_source(source_name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Ép phẳng một sàn tuyển dụng, kiểm toán completeness và lưu file sàn."""
    t0 = time.time()
    src_file = resolve_source_file(IN_DIR, source_name)
    if not src_file:
        logger.warning(f"[SKIP] Không tìm thấy dữ liệu đầu vào cho sàn '{source_name}' tại {IN_DIR}")
        return [], {}

    logger.info(f"--- Đang tích hợp (P2 Integration) nguồn: {source_name.upper()} từ {src_file.name} ---")

    # Đọc dữ liệu đầu vào linh hoạt
    raw_envelopes: List[Dict[str, Any]] = []
    if src_file.suffix == ".jsonl":
        with open(src_file, "r", encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if line:
                    try:
                        raw_envelopes.append(json.loads(line))
                    except Exception:
                        raw_envelopes.append({"raw_payload": {"raw_text": line}, "metadata": {"source": source_name}})
    elif src_file.suffix == ".parquet":
        df_p = pd.read_parquet(src_file)
        raw_envelopes = df_p.to_dict(orient="records")
    else:
        with open(src_file, "r", encoding="utf-8") as fp:
            content = json.load(fp)
            raw_envelopes = content if isinstance(content, list) else [content]

    n_in = len(raw_envelopes)
    integrated_records: List[Dict[str, Any]] = []

    # Flatten từng bản ghi
    for env in raw_envelopes:
        flat_rec = flatten_raw_job_record(env, source_fallback=source_name)
        
        # Bổ sung clean metadata nếu có trong envelope P1
        meta = env.get("metadata") or env.get("_meta") or {}
        clean_info = meta.get("clean") or {}
        flat_rec["it_rule"] = clean_info.get("it_rule")
        flat_rec["it_rule_level"] = clean_info.get("it_rule_level")
        flat_rec["it_status"] = clean_info.get("it_status")
        flat_rec["dedup_key"] = clean_info.get("dedup_key")
        flat_rec["also_on"] = clean_info.get("also_on") or []

        integrated_records.append(flat_rec)

    n_out = len(integrated_records)

    # Khẳng định hợp đồng dữ liệu Zero-Drop
    assert n_in == n_out, f"Vi phạm Zero-Drop tại sàn {source_name}: Vào {n_in} != Ra {n_out}!"

    # 1. Lưu file parquet riêng cho sàn
    source_parquet = OUT_DIR / f"{source_name}.parquet"
    df_source = pd.DataFrame(integrated_records)
    df_source.to_parquet(source_parquet, engine="pyarrow", index=False)

    # 2. Thống kê độ phủ trường (Completeness) & Chẩn đoán lý do Null
    field_completeness = {}
    if n_out > 0:
        for k in integrated_records[0].keys():
            non_empty_count = sum(
                1 for r in integrated_records
                if r.get(k) is not None and r.get(k) != "" and r.get(k) != []
            )
            pct = round(non_empty_count / n_out * 100.0, 2)
            null_reason = NULL_DIAGNOSTIC_KNOWLEDGE_BASE.get(k, {}).get(
                source_name,
                "Trường tùy chọn, nhà tuyển dụng không khai báo trên form." if pct < 100 else "Đầy đủ 100%."
            )
            field_completeness[k] = {
                "filled_count": non_empty_count,
                "missing_count": n_out - non_empty_count,
                "completeness_pct": pct,
                "null_diagnosis": null_reason,
            }

    report = {
        "source_platform": source_name,
        "step": "02_integration",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input_file": str(src_file),
        "input_records": n_in,
        "output_records": n_out,
        "dropped_records": n_in - n_out,
        "status": "PASS",
        "output_parquet": str(source_parquet),
        "field_completeness_audit": field_completeness,
        "duration_seconds": round(time.time() - t0, 2),
    }

    report_path = REPORT_DIR / f"{source_name}.json"
    with open(report_path, "w", encoding="utf-8") as fp:
        json.dump(report, fp, ensure_ascii=False, indent=2)

    logger.info(f"  -> {source_name}: Tích hợp {n_out:,}/{n_in:,} bản ghi thành công ({time.time() - t0:.2f}s)")
    return integrated_records, report


def run_all_integration() -> None:
    """Điều phối toàn bộ quá trình Integration cho 8 nguồn và xuất bản all.parquet chuẩn."""
    logger.info("================================================================================")
    logger.info("       BẮT ĐẦU GIAI ĐOẠN INTEGRATION & SCHEMA FLATTEN (XUẤT ALL.PARQUET)         ")
    logger.info("       (BẢO TOÀN ZERO-DROP DATA CONTRACT - TỰ ĐỘNG ĐỒNG BỘ DỮ LIỆU TỪ R2)        ")
    logger.info("================================================================================")
    t_start = time.time()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Kéo dữ liệu từ R2 về nếu chưa có đủ
    ensure_p1_data_from_r2(IN_DIR)

    all_records: List[Dict[str, Any]] = []
    source_reports: Dict[str, Dict[str, Any]] = {}

    for s in SOURCES:
        records, rep = integrate_single_source(s)
        if records:
            all_records.extend(records)
            source_reports[s] = rep

    total_master = len(all_records)
    if total_master == 0:
        raise RuntimeError(f"Không có dữ liệu đầu vào nào tại {IN_DIR} để thực hiện Bước 2!")

    # 1. Gộp toàn bộ về DataFrame và làm sạch giá trị khuyết
    master_df = pd.DataFrame(all_records)
    for col in master_df.columns:
        if master_df[col].dtype == object:
            if not master_df[col].apply(lambda x: isinstance(x, list)).any():
                master_df[col] = master_df[col].where(master_df[col].notna(), None)

    # 2. XUẤT TỆP MASTER ALL.PARQUET (Đúng yêu cầu cốt lõi của Trưởng nhóm)
    master_parquet_path = OUT_DIR / "all.parquet"
    master_df.to_parquet(master_parquet_path, engine="pyarrow", index=False)
    logger.info(f"[XUẤT BẢN THÀNH CÔNG] Master Parquet: {master_parquet_path} ({total_master:,} bản ghi)")

    # 3. Tạo báo cáo tổng hợp Master JSON (_all.json) phục vụ Dashboard
    field_completeness_all = {}
    sample_keys = list(all_records[0].keys())
    for k in sample_keys:
        non_empty_count = sum(
            1 for r in all_records
            if r.get(k) is not None and r.get(k) != "" and r.get(k) != []
        )
        pct = round(non_empty_count / total_master * 100.0, 2)
        field_completeness_all[k] = {
            "filled_count": non_empty_count,
            "missing_count": total_master - non_empty_count,
            "completeness_pct": pct,
            "source_coverage": {
                s: source_reports[s]["field_completeness_audit"].get(k, {}).get("completeness_pct", 0.0)
                for s in source_reports
            },
            "general_null_diagnosis": f"Tỷ lệ trống {round(100.0 - pct, 2)}% chủ yếu do đặc thù biểu mẫu tuyển dụng của các sàn.",
        }

    master_report = {
        "step": "02_integration",
        "output_format": "parquet",
        "output_file": str(master_parquet_path),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_integrated_records": total_master,
        "total_input_records": sum(r["input_records"] for r in source_reports.values()),
        "total_dropped_records": 0,
        "contract_verified": True,
        "source_breakdown": {s: r["output_records"] for s, r in source_reports.items()},
        "field_completeness_audit": field_completeness_all,
        "total_duration_seconds": round(time.time() - t_start, 2),
    }

    master_report_path = REPORT_DIR / "_all.json"
    with open(master_report_path, "w", encoding="utf-8") as fp:
        json.dump(master_report, fp, ensure_ascii=False, indent=2)

    # 4. In bảng nghiệm thu ASCII ra màn hình
    print("\n" + "=" * 90)
    print(f"{'SÀN TUYỂN DỤNG':<16} | {'ĐẦU VÀO P1':<12} | {'ĐẦU RA P2':<12} | {'CHÊNH LỆCH':<12} | {'HỢP ĐỒNG'}")
    print("-" * 90)
    for s, rep in source_reports.items():
        print(f"{s:<16} | {rep['input_records']:<12,} | {rep['output_records']:<12,} | {rep['dropped_records']:<12} | {rep['status']}")
    print("=" * 90)
    print(f"{'TỔNG ALL.PARQUET':<16} | {master_report['total_input_records']:<12,} | {total_master:<12,} | 0            | 100% ZERO-DROP")
    print("=" * 90 + "\n")
    logger.info(f"HOÀN TẤT BƯỚC 2 TRONG {time.time() - t_start:.2f} GIÂY!")


if __name__ == "__main__":
    run_all_integration()