#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VN-IT-Job-Mining Lakehouse Web Console UI (Dự phòng & Trực quan)

Khởi chạy một Web Dashboard giao diện MinIO Console trực quan ngay trên trình duyệt:
- Xem danh sách bucket và cây thư mục (url_ledger/topcv, raw/topcv, manifests)
- Xem bảng dữ liệu URL Ledger (Job ID, Tiêu đề, Công ty, Trạng thái, Lỗi)
- Xem trực tiếp nội dung các file JSON / JSONL
- Tự động phát hiện MinIO S3 Lakehouse hoặc đọc từ thư mục cục bộ data/

Sử dụng:
    python scripts/lakehouse_ui.py --port 9001
    (Hoặc --port 9002 nếu port 9001 đang được dùng bởi MinIO Docker)
"""

import argparse
import json
import os
import sys
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO_DIR = Path(__file__).resolve().parent.parent


def get_ledger_data(source: str = "topcv") -> dict:
    catalog_path = REPO_DIR / "data" / source / "url_ledger" / "catalog_master.json"
    if not catalog_path.exists():
        legacy = REPO_DIR / "data" / "url_ledger" / source / "catalog_master.json"
        if legacy.exists():
            catalog_path = legacy

    if not catalog_path.exists():
        return {"records": {}, "total": 0, "counts": {}}

    try:
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        counts = Counter(r.get("status", "UNKNOWN") for r in data.values())
        reposts = sum(1 for r in data.values() if r.get("repost_of_url_hash"))
        return {
            "records": data,
            "total": len(data),
            "counts": dict(counts),
            "reposts": reposts,
            "path": str(catalog_path),
        }
    except Exception as e:
        return {"records": {}, "total": 0, "counts": {}, "error": str(e)}


def list_files(base_sub: str = "topcv") -> list:
    results = []
    base_dir = REPO_DIR / "data" / base_sub
    if not base_dir.exists():
        return results

    for root, _, files in os.walk(base_dir):
        for f in files:
            f_path = Path(root) / f
            rel = f_path.relative_to(REPO_DIR / "data")
            results.append({
                "name": f,
                "path": str(rel),
                "size": f_path.stat().st_size,
                "modified": f_path.stat().st_mtime,
            })
    return results


HTML_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MinIO Lakehouse Console — VN-IT-Job-Mining</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0B1120; color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        .minio-red { color: #C72C41; }
        .bg-minio-red { background-color: #C72C41; }
        .bg-panel { background-color: #1E293B; }
        .border-panel { border-color: #334155; }
    </style>
</head>
<body class="flex h-screen overflow-hidden">

    <!-- Sidebar -->
    <div class="w-64 bg-slate-900 border-r border-panel flex flex-col justify-between">
        <div>
            <!-- Brand -->
            <div class="p-5 border-b border-panel flex items-center space-x-3">
                <div class="w-8 h-8 rounded bg-red-600 flex items-center justify-center font-bold text-white tracking-wider">M</div>
                <div>
                    <h1 class="font-bold text-lg text-white leading-tight">MinIO Console</h1>
                    <span class="text-xs text-slate-400">VN-IT-Job-Mining</span>
                </div>
            </div>

            <!-- Buckets Menu -->
            <div class="p-4">
                <div class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Buckets & Data</div>
                <div class="space-y-1">
                    <button class="w-full text-left px-3 py-2 rounded bg-slate-800 text-white font-medium flex items-center justify-between text-sm">
                        <span>🪣 vn-it-jobs</span>
                        <span class="text-xs bg-red-900/60 text-red-200 px-2 py-0.5 rounded">Active</span>
                    </button>
                    <button class="w-full text-left px-3 py-2 rounded hover:bg-slate-800 text-slate-300 font-medium flex items-center justify-between text-sm">
                        <span>📁 data/topcv/</span>
                        <span class="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded">Local</span>
                    </button>
                </div>
            </div>
        </div>

        <div class="p-4 border-t border-panel text-xs text-slate-400 space-y-1">
            <div>Endpoint: <span class="text-slate-200 font-mono">http://localhost:9000</span></div>
            <div>Web UI: <span class="text-slate-200 font-mono">http://localhost:9001</span></div>
            <div>Tài khoản: <span class="text-slate-200 font-mono">minioadmin</span></div>
        </div>
    </div>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
        <!-- Topbar -->
        <header class="h-16 bg-slate-900/80 border-b border-panel flex items-center justify-between px-8">
            <div class="flex items-center space-x-3">
                <span class="text-slate-400">Bucket:</span>
                <span class="text-white font-semibold text-lg">vn-it-jobs / url_ledger / topcv</span>
            </div>
            <div class="flex items-center space-x-4">
                <button onclick="location.reload()" class="px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 border border-panel rounded text-slate-200 flex items-center space-x-1.5">
                    <span>🔄</span> <span>Làm Mới</span>
                </button>
                <div class="flex items-center space-x-2 bg-emerald-950/60 border border-emerald-800 px-3 py-1 rounded-full text-xs text-emerald-400">
                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                    <span>Hệ Thống Trực Tuyến</span>
                </div>
            </div>
        </header>

        <!-- Content Area -->
        <main class="flex-1 overflow-y-auto p-8 space-y-6">
            <!-- Metric Cards -->
            <div id="metrics" class="grid grid-cols-5 gap-4">
                <div class="bg-panel border border-panel p-4 rounded-lg">
                    <div class="text-xs text-slate-400 font-medium">TỔNG URL PHÁT HIỆN</div>
                    <div id="metric-total" class="text-2xl font-bold text-white mt-1">-</div>
                </div>
                <div class="bg-panel border border-panel p-4 rounded-lg">
                    <div class="text-xs text-amber-400 font-medium">PENDING (CHỜ CÀO)</div>
                    <div id="metric-pending" class="text-2xl font-bold text-amber-300 mt-1">-</div>
                </div>
                <div class="bg-panel border border-panel p-4 rounded-lg">
                    <div class="text-xs text-emerald-400 font-medium">DONE (THÀNH CÔNG)</div>
                    <div id="metric-done" class="text-2xl font-bold text-emerald-300 mt-1">-</div>
                </div>
                <div class="bg-panel border border-panel p-4 rounded-lg">
                    <div class="text-xs text-red-400 font-medium">FAILED (LỖI SAFE SKIP)</div>
                    <div id="metric-failed" class="text-2xl font-bold text-red-300 mt-1">-</div>
                </div>
                <div class="bg-panel border border-panel p-4 rounded-lg">
                    <div class="text-xs text-purple-400 font-medium">REPOST PHÁT HIỆN</div>
                    <div id="metric-repost" class="text-2xl font-bold text-purple-300 mt-1">-</div>
                </div>
            </div>

            <!-- Table of Jobs -->
            <div class="bg-panel border border-panel rounded-lg overflow-hidden">
                <div class="px-6 py-4 border-b border-panel flex items-center justify-between">
                    <div class="font-semibold text-white">Danh Sách Link Bài Tuyển Dụng Trong Ledger</div>
                    <div class="flex items-center space-x-2">
                        <input id="search-input" onkeyup="filterJobs()" placeholder="Tìm theo Job ID, Tiêu đề, Công ty..." class="bg-slate-900 border border-panel px-3 py-1.5 rounded text-xs text-slate-200 w-64 focus:outline-none focus:border-red-500">
                        <select id="status-select" onchange="filterJobs()" class="bg-slate-900 border border-panel px-3 py-1.5 rounded text-xs text-slate-200">
                            <option value="">Tất cả trạng thái</option>
                            <option value="PENDING">PENDING</option>
                            <option value="DONE">DONE</option>
                            <option value="FAILED">FAILED</option>
                        </select>
                    </div>
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs">
                        <thead class="bg-slate-900/60 text-slate-400 uppercase tracking-wider border-b border-panel">
                            <tr>
                                <th class="py-3 px-4">#</th>
                                <th class="py-3 px-4">Job ID</th>
                                <th class="py-3 px-4">Trạng Thái</th>
                                <th class="py-3 px-4">Công Ty</th>
                                <th class="py-3 px-4">Tiêu Đề</th>
                                <th class="py-3 px-4">Ghi Chú / Lỗi</th>
                            </tr>
                        </thead>
                        <tbody id="jobs-table-body" class="divide-y divide-panel text-slate-300">
                            <tr><td colspan="6" class="text-center py-8 text-slate-500">Đang tải dữ liệu...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>
    </div>

    <!-- Modal Xem JSON -->
    <div id="json-modal" class="hidden fixed inset-0 bg-black/70 flex items-center justify-center p-6 z-50">
        <div class="bg-panel border border-panel rounded-lg w-3/4 max-h-[85vh] flex flex-col shadow-2xl">
            <div class="p-4 border-b border-panel flex items-center justify-between">
                <span id="modal-title" class="font-semibold text-white">Chi Tiết Bản Ghi</span>
                <button onclick="closeModal()" class="text-slate-400 hover:text-white text-lg font-bold">&times;</button>
            </div>
            <pre id="modal-content" class="p-4 overflow-auto text-xs font-mono text-emerald-300 flex-1"></pre>
        </div>
    </div>

    <script>
        let allJobs = [];

        async function loadData() {
            try {
                const res = await fetch('/api/ledger');
                const data = await res.json();
                document.getElementById('metric-total').innerText = data.total || 0;
                document.getElementById('metric-pending').innerText = data.counts.PENDING || 0;
                document.getElementById('metric-done').innerText = data.counts.DONE || 0;
                document.getElementById('metric-failed').innerText = data.counts.FAILED || 0;
                document.getElementById('metric-repost').innerText = data.reposts || 0;

                allJobs = Object.values(data.records || {});
                renderJobs(allJobs);
            } catch (e) {
                console.error(e);
            }
        }

        function renderJobs(jobs) {
            const tbody = document.getElementById('jobs-table-body');
            if (jobs.length === 0) {
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-8 text-slate-500">Không có bản ghi nào phù hợp.</td></tr>';
                return;
            }
            tbody.innerHTML = jobs.slice(0, 100).map((r, i) => {
                const st = r.status || 'UNKNOWN';
                const stClass = st === 'DONE' ? 'bg-emerald-900/60 text-emerald-300 border-emerald-700' :
                                st === 'FAILED' ? 'bg-red-900/60 text-red-300 border-red-700' :
                                'bg-amber-900/60 text-amber-300 border-amber-700';
                const title = r.preliminary_title || r.canonical_url;
                const err = r.error_log ? `<span class="text-red-400 text-xs">${r.error_log.slice(0, 50)}...</span>` : '-';
                return `
                    <tr class="hover:bg-slate-800/40 cursor-pointer" onclick='viewJob(${JSON.stringify(r).replace(/'/g, "&apos;")})'>
                        <td class="py-3 px-4 text-slate-500">${i + 1}</td>
                        <td class="py-3 px-4 font-mono text-red-400 font-semibold">${r.job_id || '-'}</td>
                        <td class="py-3 px-4"><span class="px-2 py-0.5 rounded border text-[10px] font-semibold ${stClass}">${st}</span></td>
                        <td class="py-3 px-4 text-slate-200 font-medium">${r.preliminary_company || 'Unknown'}</td>
                        <td class="py-3 px-4 text-slate-300">${title}</td>
                        <td class="py-3 px-4">${err}</td>
                    </tr>
                `;
            }).join('');
        }

        function filterJobs() {
            const query = document.getElementById('search-input').value.toLowerCase();
            const status = document.getElementById('status-select').value;
            const filtered = allJobs.filter(j => {
                const matchQ = !query ||
                    (j.job_id && j.job_id.toLowerCase().includes(query)) ||
                    (j.preliminary_title && j.preliminary_title.toLowerCase().includes(query)) ||
                    (j.preliminary_company && j.preliminary_company.toLowerCase().includes(query)) ||
                    (j.canonical_url && j.canonical_url.toLowerCase().includes(query));
                const matchS = !status || j.status === status;
                return matchQ && matchS;
            });
            renderJobs(filtered);
        }

        function viewJob(job) {
            document.getElementById('modal-title').innerText = `Job #${job.job_id} - ${job.preliminary_title || 'Chi Tiết'}`;
            document.getElementById('modal-content').innerText = JSON.stringify(job, null, 2);
            document.getElementById('json-modal').classList.remove('hidden');
        }

        function closeModal() {
            document.getElementById('json-modal').classList.add('hidden');
        }

        loadData();
    </script>
</body>
</html>
"""


class LakehouseHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif parsed.path == "/api/ledger":
            data = get_ledger_data("topcv")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        elif parsed.path == "/api/files":
            files = list_files("topcv")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(files, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


def run_server(port: int = 9001):
    server_address = ("", port)
    try:
        httpd = HTTPServer(server_address, LakehouseHandler)
        print("=" * 75)
        print(f"🎉 MinIO Lakehouse Web Console UI đang chạy tại: http://localhost:{port}")
        print("=" * 75)
        print("👉 Mở trình duyệt web của bạn và truy cập link trên để xem kết quả!")
        httpd.serve_forever()
    except OSError as e:
        if "Address already in use" in str(e):
            alt_port = port + 1
            print(f"⚠️ Cổng {port} đang bận (có thể do MinIO Docker đang chạy). Chuyển sang cổng {alt_port}...")
            run_server(alt_port)
        else:
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Lakehouse Web Console UI")
    parser.add_argument("--port", type=int, default=9001, help="Cổng chạy Web UI (mặc định: 9001)")
    args = parser.parse_args()
    run_server(port=args.port)
