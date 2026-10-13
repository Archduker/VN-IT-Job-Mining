# -*- coding: utf-8 -*-
"""Integration tests cho crawlers.preprocessing.eda.pipeline.EDAPipeline."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from crawlers.preprocessing.eda.pipeline import EDAPipeline, _sanitize_for_json, main
from crawlers.preprocessing.eda import text_analyzer as ta_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_RECORDS = [
    {
        "_meta": {"unified_id": "uid_1", "source": "topcv", "crawled_at": "2024-01-01"},
        "title": "Senior Python Developer",
        "company": "FPT Software",
        "salary": {
            "salary_min": 25000000, "salary_max": 40000000,
            "salary_currency": "VND", "salary_raw_text": "25-40 trieu/thang",
            "is_negotiable": False, "has_commission": None,
        },
        "description_list": ["Phat trien he thong", "Thiet ke database", "Tham gia CI/CD"],
        "requirements_list": ["Python >= 3.9", "3+ years experience"],
        "benefits_list": ["BHXH", "14 ngay phep"],
        "tags": {"skills": ["Python", "FastAPI", "Docker"]},
        "posted_date_text": "2024-01-01",
        "deadline_text": "2024-03-01",
    },
    {
        "_meta": {"unified_id": "uid_2", "source": "itviec", "crawled_at": "2024-01-02"},
        "title": "DevOps Engineer",
        "company": "VNG Corporation",
        "salary": {
            "salary_min": 2000, "salary_max": 3500,
            "salary_currency": "USD", "salary_raw_text": "2000-3500 usd/month",
            "is_negotiable": None, "has_commission": None,
        },
        "description_list": ["Quan ly Kubernetes cluster", "Thiet lap CI/CD pipeline"],
        "requirements_list": ["Kubernetes", "Terraform", "AWS"],
        "benefits_list": ["Remote work", "Stock options"],
        "tags": {"skills": ["Kubernetes", "Terraform", "AWS", "Docker"]},
        "posted_date_text": "2024-01-02",
        "deadline_text": "2024-02-28",
    },
]

MIXED_RECORDS = VALID_RECORDS + [
    None,          # phan tu khong hop le - null
    "not a dict",  # phan tu khong hop le - chuoi
    42,            # phan tu khong hop le - so nguyen
]


def _make_json_file(records, suffix=".json"):
    """Tao tep JSON tam thoi tu danh sach ban ghi."""
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    json.dump(records, tmp, ensure_ascii=False)
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestEDAPipeline(unittest.TestCase):

    # ---- 1. Pipeline chay thanh cong voi du lieu nho hop le ----
    def test_successful_run_with_valid_data(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            meta = results["run_metadata"]
            self.assertEqual(meta["status"], "SUCCESS")
            self.assertEqual(results["input_summary"]["valid_record_count"], 2)
            self.assertEqual(results["input_summary"]["invalid_element_count"], 0)
            self.assertEqual(results["input_summary"]["total_raw_elements"], 2)
        finally:
            os.unlink(path)

    # ---- 2. Du lieu co phan tu khong hop le ----
    def test_run_with_mixed_valid_and_invalid_elements(self):
        path = _make_json_file(MIXED_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            inp = results["input_summary"]
            self.assertEqual(inp["total_raw_elements"], 5)   # 2 hop le + 3 khong hop le
            self.assertEqual(inp["valid_record_count"], 2)
            self.assertEqual(inp["invalid_element_count"], 3)
            # loader_report phai ghi nhan chi tiet phan tu khong hop le
            lr = results["loader_report"]
            self.assertEqual(lr["invalid_element_count"], 3)
            self.assertEqual(len(lr["invalid_elements"]), 3)
        finally:
            os.unlink(path)

    # ---- 3. Duong dan khong ton tai ----
    def test_run_with_nonexistent_file(self):
        pipeline = EDAPipeline()
        results = pipeline.run("/path/that/does/not/exist/data.json")
        self.assertEqual(results["run_metadata"]["status"], "FAILED")
        self.assertTrue(len(results["errors"]) > 0)
        self.assertEqual(results["errors"][0]["stage"], "loader")
        self.assertEqual(results["errors"][0]["error_type"], "FileNotFoundError")

    # ---- 4. JSON khong hop le ----
    def test_run_with_invalid_json_file(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        tmp.write("{invalid_json: true,,,}")
        tmp.close()
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(tmp.name)
            self.assertEqual(results["run_metadata"]["status"], "FAILED")
            self.assertTrue(len(results["errors"]) > 0)
            # Loi phai o stage loader
            loader_err = next(
                (e for e in results["errors"] if e["stage"] == "loader"), None
            )
            self.assertIsNotNone(loader_err)
        finally:
            os.unlink(tmp.name)

    # ---- 5. Tat ca cac nhom khoa can thiet phai co mat ----
    def test_output_has_all_required_keys(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            required_keys = [
                "run_metadata", "input_summary", "loader_report",
                "profiler", "salary_analysis", "date_analysis",
                "text_analysis", "risk_analysis", "performance", "errors",
            ]
            for key in required_keys:
                self.assertIn(key, results, f"Khoa '{key}' khong co trong ket qua")
            # performance phai co cac truong con
            perf = results["performance"]
            self.assertIn("total_elapsed_seconds", perf)
            self.assertIn("stage_timings_seconds", perf)
            self.assertIn("memory", perf)
            # run_metadata phai co status va pipeline_version
            meta = results["run_metadata"]
            self.assertIn("status", meta)
            self.assertIn("pipeline_version", meta)
            self.assertIn("analysis_config", meta)
        finally:
            os.unlink(path)

    # ---- 6. Du lieu chi duoc nap mot lan ----
    def test_data_loaded_exactly_once(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            self.assertEqual(pipeline.load_count, 0)
            pipeline.run(path)
            self.assertEqual(pipeline.load_count, 1)
            # Chay lan 2 voi instance moi
            pipeline2 = EDAPipeline()
            pipeline2.run(path)
            self.assertEqual(pipeline2.load_count, 1)
        finally:
            os.unlink(path)

    # ---- 7. JSON serialization thanh cong ----
    def test_json_serialization_success(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            json_str = json.dumps(results, ensure_ascii=False)
            self.assertIsInstance(json_str, str)
            # Parse lai de dam bao round-trip hop le
            reparsed = json.loads(json_str)
            self.assertIsInstance(reparsed, dict)
        finally:
            os.unlink(path)

    # ---- 8. So lieu tong ban ghi co the doi soat giua cac module ----
    def test_record_counts_reconcile_across_modules(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            valid_count = results["input_summary"]["valid_record_count"]

            # Profiler phai bao cao cung so ban ghi
            profiler = results["profiler"]
            if profiler is not None:
                self.assertEqual(profiler["total_records"], valid_count)

            # TextAnalyzer phai bao cao cung so ban ghi
            text = results["text_analysis"]
            if text is not None:
                self.assertEqual(text["total_analyzed"], valid_count)

            # RiskDetector phai bao cao cung so ban ghi
            risk = results["risk_analysis"]
            if risk is not None:
                self.assertEqual(risk["total_analyzed"], valid_count)
        finally:
            os.unlink(path)

    # ---- 9. Khong co file dau vao nao bi thay doi ----
    def test_input_file_is_not_modified(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            original_size = os.path.getsize(path)
            original_mtime = os.path.getmtime(path)
            pipeline = EDAPipeline()
            pipeline.run(path)
            self.assertEqual(os.path.getsize(path), original_size)
            self.assertAlmostEqual(os.path.getmtime(path), original_mtime, places=1)
        finally:
            os.unlink(path)

    # ---- 10. Khong duoc xuat bao cao de len file dau vao ----
    def test_output_path_must_differ_from_input(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            with self.assertRaises(ValueError):
                pipeline.run(path, output_path=path)
        finally:
            os.unlink(path)

    # ---- 11. Analyzer that bai -> status = PARTIAL, khong bo qua loi ----
    def test_analyzer_failure_sets_status_partial_and_records_error(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()

            # Monkey-patch TextAnalyzer.analyze de gia lap loi
            from crawlers.preprocessing.eda import text_analyzer as ta_module
            original_analyze = ta_module.TextAnalyzer.analyze

            def broken_analyze(records):
                raise RuntimeError("Simulated TextAnalyzer failure")

            ta_module.TextAnalyzer.analyze = staticmethod(broken_analyze)
            try:
                results = pipeline.run(path)
            finally:
                ta_module.TextAnalyzer.analyze = original_analyze

            self.assertEqual(results["run_metadata"]["status"], "PARTIAL")
            self.assertIsNone(results["text_analysis"])
            err_stages = [e["stage"] for e in results["errors"]]
            self.assertIn("text_analyzer", err_stages)
            # Cac analyzer khac van chay
            self.assertIsNotNone(results["profiler"])
            self.assertIsNotNone(results["salary_analysis"])
        finally:
            os.unlink(path)

    # ---- 12. save_report ghi file thanh cong ----
    def test_save_report_writes_valid_json(self):
        path = _make_json_file(VALID_RECORDS)
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "report.json")
            try:
                pipeline = EDAPipeline()
                results = pipeline.run(path, output_path=out_path)
                self.assertTrue(os.path.isfile(out_path))
                with open(out_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                self.assertIn("run_metadata", loaded)
            finally:
                os.unlink(path)

    # ---- 13. _sanitize_for_json xu ly dung NaN, Infinity, set, datetime ----
    def test_sanitize_for_json(self):
        import math
        from datetime import datetime

        dirty = {
            "nan_val": float("nan"),
            "inf_val": float("inf"),
            "neg_inf": float("-inf"),
            "dt": datetime(2024, 1, 1, 12, 0, 0),
            "s": {1, 2, 3},
            "nested": {"x": float("nan"), "y": [float("inf"), "ok"]},
        }
        clean = _sanitize_for_json(dirty)
        self.assertIsNone(clean["nan_val"])
        self.assertIsNone(clean["inf_val"])
        self.assertIsNone(clean["neg_inf"])
        self.assertIsInstance(clean["dt"], str)
        self.assertIsInstance(clean["s"], list)
        self.assertIsNone(clean["nested"]["x"])
        self.assertIsNone(clean["nested"]["y"][0])
        self.assertEqual(clean["nested"]["y"][1], "ok")
        # Phai tuan tu hoa JSON duoc sau khi lam sach
        json.dumps(clean)

    # ---- 14. Performance metrics phai co mat va hop le ----
    def test_performance_metrics_present_and_valid(self):
        path = _make_json_file(VALID_RECORDS)
        try:
            pipeline = EDAPipeline()
            results = pipeline.run(path)
            perf = results["performance"]

            total = perf["total_elapsed_seconds"]
            self.assertIsInstance(total, (int, float))
            self.assertGreater(total, 0)

            timings = perf["stage_timings_seconds"]
            self.assertIn("loader", timings)
            self.assertIn("profiler", timings)

            mem = perf["memory"]
            self.assertIn("peak_traced_mb", mem)
            self.assertIn("method", mem)
            # Phuong phap do phai ghi ro la tracemalloc
            self.assertIn("tracemalloc", mem["method"].lower())
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# TestEDAPipelineCLI - Kiem thu CLI Entrypoint va Exit Codes
# ---------------------------------------------------------------------------

class TestEDAPipelineCLI(unittest.TestCase):
    """Kiem thu cac kich ban thuc thi CLI va ma thoat (Exit Codes) cua EDAPipeline."""

    def setUp(self):
        self.tmpdir_obj = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self.tmpdir_obj.name)
        self.valid_input_path = self.tmpdir / "valid_jobs.json"
        with open(self.valid_input_path, "w", encoding="utf-8") as f:
            json.dump(VALID_RECORDS, f, ensure_ascii=False)

    def tearDown(self):
        self.tmpdir_obj.cleanup()

    # 1. SUCCESS -> exit code 0 (ca mac dinh va khi co --fail-on-partial)
    def test_cli_success_default_and_with_flag(self):
        out_path = self.tmpdir / "report_success.json"
        exit_code = main([str(self.valid_input_path), str(out_path)])
        self.assertEqual(exit_code, 0)
        self.assertTrue(out_path.is_file())
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["run_metadata"]["status"], "SUCCESS")

        # Khi co flag --fail-on-partial, status la SUCCESS van phai tra ve 0
        out_flag = self.tmpdir / "report_success_flag.json"
        exit_code_flag = main([str(self.valid_input_path), str(out_flag), "--fail-on-partial"])
        self.assertEqual(exit_code_flag, 0)

    # 2. PARTIAL mac dinh -> exit code 0
    def test_cli_partial_default_returns_zero(self):
        out_path = self.tmpdir / "report_partial_default.json"
        original_analyze = ta_module.TextAnalyzer.analyze

        def broken_analyze(records):
            raise RuntimeError("Simulated TextAnalyzer failure")

        ta_module.TextAnalyzer.analyze = staticmethod(broken_analyze)
        try:
            exit_code = main([str(self.valid_input_path), str(out_path)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_path.is_file())
            with open(out_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["run_metadata"]["status"], "PARTIAL")
        finally:
            ta_module.TextAnalyzer.analyze = original_analyze

    # 3. PARTIAL voi --fail-on-partial -> exit code 2
    def test_cli_partial_with_fail_on_partial_returns_two(self):
        out_path = self.tmpdir / "report_partial_flag.json"
        original_analyze = ta_module.TextAnalyzer.analyze

        def broken_analyze(records):
            raise RuntimeError("Simulated TextAnalyzer failure")

        ta_module.TextAnalyzer.analyze = staticmethod(broken_analyze)
        try:
            exit_code = main([str(self.valid_input_path), str(out_path), "--fail-on-partial"])
            self.assertEqual(exit_code, 2)
            self.assertTrue(out_path.is_file())
            with open(out_path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["run_metadata"]["status"], "PARTIAL")
        finally:
            ta_module.TextAnalyzer.analyze = original_analyze

    # 4. FAILED -> exit code 1 (file khong ton tai, JSON loi, hoac co --fail-on-partial)
    def test_cli_failed_returns_one(self):
        out_path = self.tmpdir / "report_failed.json"
        non_existent = self.tmpdir / "does_not_exist.json"

        # 4a. File khong ton tai
        exit_code_nonexistent = main([str(non_existent), str(out_path)])
        self.assertEqual(exit_code_nonexistent, 1)

        # 4b. JSON hong cu phap
        bad_json_path = self.tmpdir / "malformed.json"
        with open(bad_json_path, "w", encoding="utf-8") as f:
            f.write("{\ninvalid json syntax")
        exit_code_malformed = main([str(bad_json_path), str(out_path)])
        self.assertEqual(exit_code_malformed, 1)

        # 4c. FAILED kem flag --fail-on-partial van phai tra ve 1 (khong phai 2)
        exit_code_flag = main([str(non_existent), str(out_path), "--fail-on-partial"])
        self.assertEqual(exit_code_flag, 1)

    # 5. --help hoat dong va tra ve exit code 0
    def test_cli_help_flag(self):
        proc = subprocess.run(
            [sys.executable, "crawlers/preprocessing/eda/pipeline.py", "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--fail-on-partial", proc.stdout)
        self.assertIn("input_path", proc.stdout)
        self.assertIn("output_path", proc.stdout)

    # 6. Positional arguments cu van hoat dong (Subprocess end-to-end)
    def test_cli_positional_arguments_via_subprocess(self):
        out_path = self.tmpdir / "report_subprocess.json"
        proc = subprocess.run(
            [
                sys.executable,
                "crawlers/preprocessing/eda/pipeline.py",
                str(self.valid_input_path),
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertTrue(out_path.is_file())
        with open(out_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["run_metadata"]["status"], "SUCCESS")

    # 7. Subprocess voi file khong ton tai tra ve exit code 1
    def test_cli_subprocess_failed_exit_code(self):
        out_path = self.tmpdir / "report_sub_fail.json"
        proc = subprocess.run(
            [
                sys.executable,
                "crawlers/preprocessing/eda/pipeline.py",
                str(self.tmpdir / "missing.json"),
                str(out_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Status : FAILED", proc.stdout)


if __name__ == "__main__":
    unittest.main()
