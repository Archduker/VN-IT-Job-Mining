"""
Unit tests for crawlers.common.checkpoint
"""

import json
from pathlib import Path
from crawlers.common.checkpoint import CheckpointManager


def test_checkpoint_init_creates_dir(tmp_path: Path):
    ckpt_dir = tmp_path / "checkpoints"
    manager = CheckpointManager(source="topdev", checkpoint_dir=ckpt_dir)
    assert ckpt_dir.exists()
    assert manager.source == "topdev"
    assert manager.last_page == 0
    assert len(manager.seen_ids) == 0


def test_checkpoint_save_and_load(tmp_path: Path):
    ckpt_dir = tmp_path / "checkpoints"
    manager = CheckpointManager(source="topdev", checkpoint_dir=ckpt_dir)
    manager.mark_seen("job_101")
    manager.mark_seen("job_102")
    manager.update_page(3)
    manager.set_extra("cursor", "abc_xyz")
    manager.save()

    # Create new manager pointing to same directory
    new_manager = CheckpointManager(source="topdev", checkpoint_dir=ckpt_dir)
    assert new_manager.last_page == 3
    assert new_manager.is_seen("job_101")
    assert new_manager.is_seen("job_102")
    assert not new_manager.is_seen("job_103")
    assert new_manager.total_collected == 2
    assert new_manager.get_extra("cursor") == "abc_xyz"


def test_checkpoint_is_seen_and_mark_seen(tmp_path: Path):
    manager = CheckpointManager(source="careerviet", checkpoint_dir=tmp_path)
    assert not manager.is_seen("12345")
    assert manager.mark_seen("12345") is True
    assert manager.is_seen("12345") is True
    # Duplicate mark returns False
    assert manager.mark_seen("12345") is False
    assert manager.total_collected == 1


def test_checkpoint_reset(tmp_path: Path):
    manager = CheckpointManager(source="itviec", checkpoint_dir=tmp_path)
    manager.mark_seen("itv_1")
    manager.update_page(5)
    manager.save()
    assert manager.file_path.exists()

    manager.reset()
    assert manager.last_page == 0
    assert len(manager.seen_ids) == 0
    assert not manager.file_path.exists()
