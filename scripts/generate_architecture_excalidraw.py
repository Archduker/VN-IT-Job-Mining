#!/usr/bin/env python3
"""
Generator script for docs/architecture/data_collection_architecture.excalidraw
Creates a complete, professionally styled Excalidraw diagram covering:
1. System Architecture (with styled technology badges/logos: Airflow, Python, Playwright, SQLite, AWS S3, Pydantic, PostgreSQL, Terminal Dashboard)
2. End-to-End Data Flow Pipeline (Step-by-step from portal scraping to Data Quality and S3 Storage)
"""

import json
import time

def generate_excalidraw():
    now_ms = int(time.time() * 1000)
    elements = []
    element_id_counter = 0

    def next_id(prefix="elem"):
        nonlocal element_id_counter
        element_id_counter += 1
        return f"{prefix}_{element_id_counter}"

    def add_rect(x, y, w, h, bg="#ffffff", stroke="#1e1e1e", stroke_w=2, stroke_s="solid", roundness=3, roughness=1, opacity=100):
        elem_id = next_id("rect")
        elements.append({
            "id": elem_id,
            "type": "rectangle",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "strokeColor": stroke,
            "backgroundColor": bg,
            "fillStyle": "solid",
            "strokeWidth": stroke_w,
            "strokeStyle": stroke_s,
            "roughness": roughness,
            "opacity": opacity,
            "roundness": {"type": roundness} if roundness else None,
            "version": 1,
            "versionNonce": 1000000 + len(elements),
            "isDeleted": False,
            "angle": 0,
            "seed": len(elements) + 1,
            "groupIds": [],
            "frameId": None,
            "boundElements": [],
            "updated": now_ms,
            "link": None,
            "locked": False
        })
        return elem_id

    def add_text(x, y, text, font_size=16, font_fam=6, color="#1e1e1e", align="center", line_height=1.25):
        elem_id = next_id("text")
        lines = text.split("\n")
        w = max(len(line) for line in lines) * (font_size * 0.6)
        h = len(lines) * (font_size * line_height)
        elements.append({
            "id": elem_id,
            "type": "text",
            "x": x,
            "y": y,
            "width": w,
            "height": h,
            "text": text,
            "fontSize": font_size,
            "fontFamily": font_fam,
            "textAlign": align,
            "verticalAlign": "top",
            "version": 1,
            "versionNonce": 2000000 + len(elements),
            "isDeleted": False,
            "fillStyle": "solid",
            "strokeWidth": 1,
            "strokeStyle": "solid",
            "roughness": 1,
            "opacity": 100,
            "angle": 0,
            "strokeColor": color,
            "backgroundColor": "transparent",
            "seed": len(elements) + 1,
            "groupIds": [],
            "frameId": None,
            "roundness": None,
            "boundElements": [],
            "updated": now_ms,
            "link": None,
            "locked": False,
            "containerId": None,
            "originalText": text,
            "autoResize": True,
            "lineHeight": line_height
        })
        return elem_id

    def add_badge(x, y, w, h, bg_color, border_color, icon_text, label_text, sub_text=""):
        # Outer container pill
        add_rect(x, y, w, h, bg=bg_color, stroke=border_color, stroke_w=2, roundness=3, roughness=0)
        # Icon / Logo graphic block on the left
        icon_w = 34
        add_rect(x + 6, y + (h - 28)//2, icon_w, 28, bg="#ffffff", stroke=border_color, stroke_w=1, roundness=2, roughness=0)
        add_text(x + 10, y + (h - 24)//2, icon_text, font_size=14, color=border_color, align="center")
        # Text block
        if sub_text:
            add_text(x + icon_w + 12, y + 6, label_text, font_size=13, color="#1e1e1e", align="left")
            add_text(x + icon_w + 12, y + 22, sub_text, font_size=10, color="#555555", align="left")
        else:
            add_text(x + icon_w + 12, y + (h - 18)//2, label_text, font_size=13, color="#1e1e1e", align="left")

    def add_arrow(start_x, start_y, end_x, end_y, stroke="#1e1e1e", stroke_w=2, stroke_s="solid", label=""):
        elem_id = next_id("arrow")
        dx = end_x - start_x
        dy = end_y - start_y
        elements.append({
            "id": elem_id,
            "type": "arrow",
            "x": start_x,
            "y": start_y,
            "width": abs(dx),
            "height": abs(dy),
            "strokeColor": stroke,
            "strokeWidth": stroke_w,
            "strokeStyle": stroke_s,
            "roughness": 1,
            "opacity": 100,
            "angle": 0,
            "backgroundColor": "transparent",
            "seed": len(elements) + 1,
            "groupIds": [],
            "frameId": None,
            "roundness": None,
            "boundElements": [],
            "updated": now_ms,
            "link": None,
            "locked": False,
            "points": [[0, 0], [dx, dy]],
            "lastCommittedPoint": None,
            "version": 1,
            "versionNonce": 3000000 + len(elements),
            "isDeleted": False,
            "fillStyle": "solid",
            "startBinding": None,
            "endBinding": None,
            "startArrowhead": None,
            "endArrowhead": "arrow"
        })
        if label:
            mid_x = start_x + dx * 0.45
            mid_y = start_y + dy * 0.45 - 16
            add_text(mid_x, mid_y, label, font_size=12, color=stroke, align="center")
        return elem_id

    # =========================================================================
    # HEADER BANNER
    # =========================================================================
    add_rect(40, 30, 1520, 90, bg="#f8f9fa", stroke="#2b8a3e", stroke_w=2, roundness=3, roughness=0)
    add_text(80, 42, "VN-IT-JOB-MINING — KIẾN TRÚC THU THẬP & LUỒNG DỮ LIỆU ĐẦU-CUỐI", font_size=24, color="#1e1e1e", align="left")
    add_text(80, 78, "Hệ Thống 8 Nguồn Tuyển Dụng | 9 Airflow DAGs | Data Contract Schema v1 | O(1) Deduplication | AWS S3 Raw Lake", font_size=14, color="#495057", align="left")

    # =========================================================================
    # PART A: SYSTEM ARCHITECTURE (Y: 140 -> 820)
    # =========================================================================
    # Section Header
    add_rect(40, 140, 1520, 40, bg="#e7f5ff", stroke="#1971c2", stroke_w=2, roundness=2, roughness=0)
    add_text(60, 148, "PHẦN A: KIẾN TRÚC HỆ THỐNG TỔNG THỂ (SYSTEM ARCHITECTURE)", font_size=18, color="#1864ab", align="left")

    # Technology Badges Bar (Showcasing all technologies with branded colors)
    badge_y = 195
    add_badge(60, badge_y, 160, 40, bg_color="#e7f5ff", border_color="#017cee", icon_text="🌪️", label_text="Airflow 2.11+", sub_text="Orchestration")
    add_badge(235, badge_y, 160, 40, bg_color="#fff9db", border_color="#e67700", icon_text="🐍", label_text="Python 3.10+", sub_text="Core Framework")
    add_badge(410, badge_y, 160, 40, bg_color="#ebfbee", border_color="#2b8a3e", icon_text="🎭", label_text="Playwright", sub_text="Headless Chrome")
    add_badge(585, badge_y, 160, 40, bg_color="#f3f0ff", border_color="#7048e8", icon_text="🍲", label_text="BS4 & Requests", sub_text="Fast SSR Parser")
    add_badge(760, badge_y, 160, 40, bg_color="#e6fcf5", border_color="#0ca678", icon_text="🗄️", label_text="SQLite Catalog", sub_text="O(1) State Dedup")
    add_badge(935, badge_y, 160, 40, bg_color="#fff0f6", border_color="#d6336c", icon_text="🛡️", label_text="Pydantic v2", sub_text="Data Contract v1")
    add_badge(1110, badge_y, 160, 40, bg_color="#fff4e6", border_color="#f76707", icon_text="☁️", label_text="AWS S3", sub_text="Raw Data Lake")
    add_badge(1285, badge_y, 160, 40, bg_color="#f1f3f5", border_color="#343a40", icon_text="📊", label_text="Live Monitor", sub_text="Terminal / CLI")

    # Layer 1: Data Sources Container (8 Sources)
    sources_box_y = 255
    add_rect(60, sources_box_y, 1480, 110, bg="#fafafa", stroke="#adb5bd", stroke_w=2, stroke_s="dashed", roundness=3, roughness=0)
    add_text(75, sources_box_y + 10, "1. NGUỒN DỮ LIỆU TUYỂN DỤNG CNTT (8 JOB PORTALS)", font_size=14, color="#495057", align="left")

    sources_info = [
        ("TopDev", "REST API v2", "api.topdev.vn", "#017cee", "2,818 jobs"),
        ("VietnamWorks", "Search API", "ms.vietnamworks.com", "#1971c2", "2,224 jobs"),
        ("CareerViet", "HTML SSR", "careerviet.vn", "#2f9e44", "655 jobs"),
        ("ITviec", "SSR + Sections", "itviec.com", "#e03131", "674 jobs"),
        ("TopCV", "Playwright WAF", "topcv.vn", "#0ca678", "791 jobs"),
        ("ViecLam24h", "Next.js State", "vieclam24h.vn", "#f08c00", "445 jobs"),
        ("Glints", "API / Next.js", "glints.com/vn", "#ae3ec9", "244 jobs"),
        ("JobsGO", "Playwright + BS4", "jobsgo.vn", "#1098ad", "1,476 jobs"),
    ]

    for i, (name, proto, url, col, count) in enumerate(sources_info):
        sx = 80 + i * 180
        sy = sources_box_y + 35
        add_rect(sx, sy, 165, 60, bg="#ffffff", stroke=col, stroke_w=2, roundness=2, roughness=0)
        add_text(sx + 10, sy + 6, f"🌐 {name}", font_size=13, color=col, align="left")
        add_text(sx + 10, sy + 24, f"{proto} | {count}", font_size=11, color="#212529", align="left")
        add_text(sx + 10, sy + 40, url, font_size=9, color="#868e96", align="left")

    # Layer 2: Orchestration Layer (Apache Airflow 9 DAGs)
    airflow_y = 390
    add_rect(60, airflow_y, 420, 215, bg="#e7f5ff", stroke="#017cee", stroke_w=2, roundness=3, roughness=0)
    add_text(75, airflow_y + 12, "2. TẦNG ĐIỀU PHỐI (APACHE AIRFLOW 2.11+)", font_size=15, color="#017cee", align="left")
    add_text(75, airflow_y + 35, "🌪️ Airflow Scheduler & Webserver (Port 8080)", font_size=13, color="#1e1e1e", align="left")
    
    add_rect(75, airflow_y + 60, 390, 80, bg="#ffffff", stroke="#74c0fc", stroke_w=1, roundness=2, roughness=0)
    add_text(85, airflow_y + 68, "• 7 Daily Rotating DAGs (20:00 Hàng ngày):\n  crawler_topdev ... crawler_glints\n• 1 Master Weekly DAG: crawler_weekly_all (CN 22:00)\n• 1 Periodic 4-day DAG: periodic_it_job_mining_4days", font_size=11, color="#343a40", align="left")

    add_rect(75, airflow_y + 150, 390, 45, bg="#ffffff", stroke="#74c0fc", stroke_w=1, roundness=2, roughness=0)
    add_text(85, airflow_y + 156, "Operators: JobCrawlerOp, DataQualityOp, CrawlSummaryOp\nCallbacks: _on_crawl_success, _on_crawl_failure", font_size=10, color="#1864ab", align="left")

    # Layer 3: Crawler Engine & Defense Layer
    engine_y = 390
    add_rect(510, engine_y, 530, 215, bg="#f8f9fa", stroke="#3776ab", stroke_w=2, roundness=3, roughness=0)
    add_text(525, engine_y + 12, "3. ĐỘNG CƠ THU THẬP & PHÒNG VỆ (BASECRAWLER ENGINE)", font_size=15, color="#3776ab", align="left")
    
    # 4 sub-boxes in engine
    add_rect(525, engine_y + 40, 240, 75, bg="#ffffff", stroke="#2b8a3e", stroke_w=1, roundness=2, roughness=0)
    add_text(535, engine_y + 48, "🛡️ HttpClient & Anti-Scraping", font_size=12, color="#2b8a3e", align="left")
    add_text(535, engine_y + 68, "- User-Agent Rotation (Real browsers)\n- Polite Delay: 1.5s - 3.5s\n- Exponential Backoff & Retries (3x)", font_size=10, color="#495057", align="left")

    add_rect(785, engine_y + 40, 240, 75, bg="#ffffff", stroke="#0ca678", stroke_w=1, roundness=2, roughness=0)
    add_text(795, engine_y + 48, "🗄️ SQLite State Catalog & Checkpoint", font_size=12, color="#0ca678", align="left")
    add_text(795, engine_y + 68, "- job_catalog.db (O(1) deduplication)\n- <source>_checkpoint.json (atomic)\n- Tránh cào lại tin đã SUCCESS", font_size=10, color="#495057", align="left")

    add_rect(525, engine_y + 125, 240, 70, bg="#ffffff", stroke="#d6336c", stroke_w=1, roundness=2, roughness=0)
    add_text(535, engine_y + 133, "🛡️ Pydantic Schema v1 & Clean Text", font_size=12, color="#d6336c", align="left")
    add_text(535, engine_y + 153, "- JobRecord: _meta, raw, salary, tags\n- Strip HTML & bullets cleanup\n- Language detection: 'vi' | 'en'", font_size=10, color="#495057", align="left")

    add_rect(785, engine_y + 125, 240, 70, bg="#ffffff", stroke="#e67700", stroke_w=1, roundness=2, roughness=0)
    add_text(795, engine_y + 133, "💾 JsonWriter (Atomic Array)", font_size=12, color="#e67700", align="left")
    add_text(795, engine_y + 153, "- Ghi file tạm .tmp rồi đổi tên\n- Đảm bảo JSON mảng [ ... ] toàn vẹn\n- Phân vùng Hive: dt=YYYY-MM-DD", font_size=10, color="#495057", align="left")

    # Layer 4: Quality Gate & Storage
    storage_y = 390
    add_rect(1070, storage_y, 470, 215, bg="#fff4e6", stroke="#f76707", stroke_w=2, roundness=3, roughness=0)
    add_text(1085, storage_y + 12, "4. CHẤT LƯỢNG & LƯU TRỮ (QUALITY GATE & LAKE)", font_size=15, color="#d9480f", align="left")

    add_rect(1085, storage_y + 40, 440, 45, bg="#ffffff", stroke="#2f9e44", stroke_w=1, roundness=2, roughness=0)
    add_text(1095, storage_y + 46, "✅ DataQualityOperator (Kiểm định chất lượng tự động)", font_size=12, color="#2b8a3e", align="left")
    add_text(1095, storage_y + 64, "Schema validity >= 95% (Thực tế: 100%) | Dedup = 0% | Required fields", font_size=10, color="#495057", align="left")

    add_rect(1085, storage_y + 95, 210, 100, bg="#ffffff", stroke="#1971c2", stroke_w=1, roundness=2, roughness=0)
    add_text(1095, storage_y + 103, "📁 Local Raw Lake (JSON)", font_size=12, color="#1864ab", align="left")
    add_text(1095, storage_y + 123, "data/<source>/dt=.../batch_*.json\n• 9,327 bản ghi Catalog\n• 9,038 tin sạch hợp nhất\n• 195/195 Unit Tests Pass", font_size=10, color="#343a40", align="left")

    add_rect(1315, storage_y + 95, 210, 100, bg="#ffffff", stroke="#f76707", stroke_w=1, roundness=2, roughness=0)
    add_text(1325, storage_y + 103, "☁️ AWS S3 Data Lake", font_size=12, color="#d9480f", align="left")
    add_text(1325, storage_y + 123, "s3://vn-it-jobs-raw/...\n• Độ bền 99.999999999%\n• Đồng bộ qua boto3\n• Sẵn sàng nạp PostgreSQL", font_size=10, color="#343a40", align="left")

    # Layer 5: Live Monitoring & Operations Bar
    ops_y = 625
    add_rect(60, ops_y, 1480, 85, bg="#212529", stroke="#495057", stroke_w=2, roundness=3, roughness=0)
    add_text(80, ops_y + 12, "💻 TẦNG VẬN HÀNH & GIÁM SÁT THỜI GIAN THỰC (LIVE MONITORING & OPERATIONS)", font_size=14, color="#51cf66", align="left")
    add_text(80, ops_y + 36, "• Lệnh vận hành 1-click:  make start-airflow  (Chạy ngầm Scheduler + Webserver có PID) |  make monitor  (Dashboard live terminal) |  make stop-airflow\n• Nguồn dữ liệu giám sát: SQLite State Catalog (job_catalog.db) + Checkpoints + JSON Batches + Airflow Metadata DB (airflow.db)\n• Báo cáo kiểm toán: Tự động xuất JSON summary mẻ cào vào logs/crawl_reports/crawl_report_YYYY-MM-DD.json", font_size=11, color="#f8f9fa", align="left")

    # Connective Arrows for Part A
    add_arrow(800, 365, 800, 390, stroke="#1e1e1e", stroke_w=2, label="Trích xuất dữ liệu")
    add_arrow(480, 497, 510, 497, stroke="#017cee", stroke_w=2, label="Kích hoạt task")
    add_arrow(1040, 497, 1070, 497, stroke="#d6336c", stroke_w=2, label="Kiểm định & Ghi lake")

    # =========================================================================
    # PART B: END-TO-END DATA FLOW PIPELINE (Y: 740 -> 1480)
    # =========================================================================
    add_rect(40, 740, 1520, 40, bg="#f3f0ff", stroke="#7048e8", stroke_w=2, roundness=2, roughness=0)
    add_text(60, 748, "PHẦN B: SƠ ĐỒ LUỒNG DỮ LIỆU ĐẦU-CUỐI (END-TO-END DATA FLOW PIPELINE)", font_size=18, color="#5f3dc4", align="left")

    flow_steps = [
        ("BƯỚC 1: LẬP LỊCH & KÍCH HOẠT", "Airflow Scheduler kích hoạt DAG\ntheo cron (Daily 20:00 / Weekly CN 22:00\nhoặc lệnh trigger CLI)", "#017cee", "#e7f5ff"),
        ("BƯỚC 2: QUÉT LISTING & THU THẬP ID", "HarvestListingOperator quét danh sách\nngoài trang để bóc tách cặp\n(source_job_id, job_url)", "#1971c2", "#e7f5ff"),
        ("BƯỚC 3: KHỬ TRÙNG LẬP O(1) TẬP TRUNG", "Đối chiếu SQLite Catalog (job_catalog.db):\n• Nếu đã có SUCCESS -> SKIP BỎ QUA\n• Nếu MỚI hoặc FAILED -> Đưa vào hàng đợi", "#0ca678", "#e6fcf5"),
        ("BƯỚC 4: DETAIL WORKER CÀO CHI TIẾT", "DetailCrawlerQueueOperator rút tin từ queue:\n• Rate limiter: Polite Delay 1.5s - 3.5s\n• Playwright (TopCV, JobsGO) / Requests (Khác)", "#2b8a3e", "#ebfbee"),
        ("BƯỚC 5: LÀM SẠCH VĂN BẢN & LƯƠNG", "Text Processing & Regex Utilities:\n• Strip HTML tags, tách bullet lines sạch\n• Bóc tách lương số học: min, max, currency\n• Phân loại 3 nhóm thẻ: req, skills, benefits", "#e67700", "#fff9db"),
        ("BƯỚC 6: ÉP CHUẨN PYDANTIC SCHEMA V1", "Pydantic JobRecord Validation:\n• _meta: source, dedup_key, language, batch\n• raw: salary, tags, description_list, ...\n• Smart Adapter tương thích ngược", "#d6336c", "#fff0f6"),
        ("BƯỚC 7: GHI FILE NGUYÊN TỬ (ATOMIC WRITE)", "JsonWriter ghi mảng JSON uncompressed:\n• Ghi ra file tạm batch_XXX.tmp\n• Flush & Atomic rename sang batch_XXX.json\n• Lưu tại data/<source>/dt=YYYY-MM-DD/", "#ae3ec9", "#f8f0fc"),
        ("BƯỚC 8: KIỂM ĐỊNH CHẤT LƯỢNG & ĐỒNG BỘ", "DataQualityOperator & S3 Uploader:\n• Verify schema validity >= 95%, dedup = 0%\n• Nếu PASS: Xuất CrawlSummary & Sync AWS S3\n• Nếu FAIL: Dừng pipeline & Cảnh báo", "#d9480f", "#fff4e6")
    ]

    # Two rows of 4 steps each
    # Row 1: Steps 1, 2, 3, 4 (left to right)
    r1_y = 810
    step_w = 340
    step_h = 135

    for idx in range(4):
        title, desc, col, bg_col = flow_steps[idx]
        sx = 80 + idx * 370
        add_rect(sx, r1_y, step_w, step_h, bg=bg_col, stroke=col, stroke_w=2, roundness=3, roughness=0)
        add_text(sx + 15, r1_y + 12, title, font_size=13, color=col, align="left")
        add_text(sx + 15, r1_y + 36, desc, font_size=11, color="#212529", align="left")
        if idx < 3:
            add_arrow(sx + step_w, r1_y + step_h//2, sx + step_w + 30, r1_y + step_h//2, stroke=col, stroke_w=2)

    # Arrow connecting Row 1 to Row 2 (turning down and back left)
    add_arrow(80 + 3 * 370 + step_w//2, r1_y + step_h, 80 + 3 * 370 + step_w//2, r1_y + step_h + 40, stroke="#2b8a3e", stroke_w=2, label="Đẩy payload")

    # Row 2: Steps 5, 6, 7, 8 (right to left or left to right)
    r2_y = 990
    for idx in range(4):
        step_idx = 4 + idx
        title, desc, col, bg_col = flow_steps[step_idx]
        # Draw from right to left so flow continues naturally: step 4 (top right) -> step 5 (bottom right) -> ... -> step 8 (bottom left)
        sx = 80 + (3 - idx) * 370
        add_rect(sx, r2_y, step_w, step_h, bg=bg_col, stroke=col, stroke_w=2, roundness=3, roughness=0)
        add_text(sx + 15, r2_y + 12, title, font_size=13, color=col, align="left")
        add_text(sx + 15, r2_y + 36, desc, font_size=11, color="#212529", align="left")
        if idx < 3:
            # Arrow pointing leftwards
            add_arrow(sx, r2_y + step_h//2, sx - 30, r2_y + step_h//2, stroke=col, stroke_w=2)

    # Final Outcome Banner at bottom
    out_y = 1155
    add_rect(60, out_y, 1480, 85, bg="#ebfbee", stroke="#2b8a3e", stroke_w=2, roundness=3, roughness=0)
    add_text(80, out_y + 14, "🏆 KẾT QUẢ ĐẦU RA HOÀN CHỈNH (DATA ASSET & SYSTEM READINESS)", font_size=16, color="#2b8a3e", align="left")
    add_text(80, out_y + 40, "• 9,038 Tin Việc Làm IT Sạch (9,327 trong State Catalog): 100% khớp Compact Schema v1 | 0% Trùng lặp | Lương số học min/max | Phân loại thẻ 3 chiều | Không còn rác HTML\n• 195/195 Unit Tests Passed (0.47s) | PreClean Pipeline Hợp Nhất Đa Nguồn | Sẵn sàng cho Giai đoạn 2 (EDA & NLP Khám phá Dữ liệu)", font_size=12, color="#212529", align="left")

    return {
        "type": "excalidraw",
        "version": 2,
        "source": "https://marketplace.visualstudio.com/items?itemName=pomdtr.excalidraw-editor",
        "elements": elements,
        "appState": {
            "gridSize": 20,
            "gridStep": 5,
            "gridModeEnabled": False,
            "viewBackgroundColor": "#ffffff"
        },
        "files": {}
    }

if __name__ == "__main__":
    data = generate_excalidraw()
    output_path = "docs/architecture/data_collection_architecture.excalidraw"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Generated {output_path} with {len(data['elements'])} elements successfully!")
