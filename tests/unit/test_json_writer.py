# -*- coding: utf-8 -*-
"""JsonWriter (layout batch cũ) không được tạo thư mục data/<nguồn>/dt=<ngày>/ khi không ghi gì.

BaseCrawler tạo JsonWriter ở mọi lần chạy, nên trước 03/11/2026 mỗi lần cào 2 pha đều để lại thư mục rỗng theo
layout đã bỏ (docs/issue_log.md L-23).
"""

from collection.common.json_writer import JsonWriter


def test_no_folder_when_nothing_written(tmp_path):
    writer = JsonWriter(source="topcv", output_dir=str(tmp_path))
    writer.close()
    assert not (tmp_path / "topcv").exists()


def test_writes_batch_when_records_exist(tmp_path):
    writer = JsonWriter(source="topcv", output_dir=str(tmp_path), validate_schema=False)
    writer.write({"job_id": "1"})
    writer.close()
    assert writer.file_path.exists() and writer.file_path.parent.name.startswith("dt=")
