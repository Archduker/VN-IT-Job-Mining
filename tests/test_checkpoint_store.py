# -*- coding: utf-8 -*-
"""Unit tests for CheckpointStore."""

from pathlib import Path
from preprocessing.missing_outlier.checkpoint_store import CheckpointStore


def test_checkpoint_store_lifecycle(tmp_path: Path):
    ckp_path = tmp_path / "test_checkpoint.jsonl"
    store = CheckpointStore(ckp_path)

    # Ban đầu rỗng
    assert store.count() == 0
    assert store.load_completed_ids() == set()

    # Append 2 records
    r1 = {"job_id_global": "topcv_001", "job_title": "Python Developer"}
    r2 = {"job_id_global": "itviec_002", "job_title": "Java Architect"}
    store.append_record(r1)
    store.append_record(r2)

    assert store.count() == 2
    assert store.load_completed_ids() == {"topcv_001", "itviec_002"}

    # Nạp lại từ đĩa (mô phỏng restart tiến trình)
    new_instance = CheckpointStore(ckp_path)
    assert new_instance.load_completed_ids() == {"topcv_001", "itviec_002"}
    all_recs = new_instance.load_all_records()
    assert len(all_recs) == 2
    assert all_recs[0]["job_id_global"] == "topcv_001"
    assert all_recs[1]["job_id_global"] == "itviec_002"

    # Xóa
    store.clear()
    assert store.count() == 0
    assert not ckp_path.is_file()


def test_checkpoint_handles_corrupted_lines(tmp_path: Path):
    ckp_path = tmp_path / "corrupted.jsonl"
    with ckp_path.open("w", encoding="utf-8") as f:
        f.write('{"job_id_global": "job_1"}\n')
        f.write("CORRUPTED NOT JSON LINE\n")
        f.write('{"job_id_global": "job_2"}\n')

    store = CheckpointStore(ckp_path)
    completed = store.load_completed_ids()
    assert completed == {"job_1", "job_2"}
    assert store.count() == 2
