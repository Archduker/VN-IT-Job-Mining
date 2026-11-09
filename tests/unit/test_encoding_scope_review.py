"""Scope retrieval is not a classifier; impact previews never change input X."""

import numpy as np
import pytest

from preprocessing.encoding.scope_review import impact_preview, scan_queue
from preprocessing.encoding.skills_taxonomy_230 import TAXONOMY_230


def test_queue_is_deduplicated_reproducible_and_has_no_decision():
    row = dict(job_id_global="one", source_platform="topcv", job_title="Kỹ sư QA/QC xây dựng",
               job_family="Kiểm thử (QA/QC)", description_clean="Thi công xây dựng, công trường và hồ sơ nghiệm thu.",
               requirements_clean="Biết AutoCAD, Python và phần mềm văn phòng.")
    queue, hits = scan_queue([row], {"one"})
    assert len(queue) == 1 and "S00_AUTOCAD_SEED" in queue[0]["rule_ids"]
    assert queue[0]["keyword_not_scope_decision"] is True
    assert "proposed_decision" not in queue[0]
    for hit in hits:
        if hit["field"] != "skills_std":
            assert row[hit["field"]][hit["match_start"]:hit["match_end"]] == hit["match"]
    assert (queue, hits) == scan_queue([row], {"one"})


def test_it_word_does_not_override_candidates_and_cnc_can_be_place_name():
    row = dict(job_id_global="one", source_platform="topcv", job_title="C# Developer", job_family="Backend",
               description_clean="Phát triển ứng dụng backend và API cho phần mềm.", requirements_clean="Làm việc tại Khu CNC Hòa Lạc.")
    queue, _ = scan_queue([row], set())
    assert len(queue) == 1 and queue[0]["it_counter_signals"]
    assert "proposed_decision" not in queue[0]  # human review can retain this role


def test_impact_keeps230_order_and_reports_new_zero_without_padding():
    items = [dict(canonical="AutoCAD", column="skill_autocad")] + [dict(canonical=e.canonical, column=e.column_name) for e in TAXONOMY_230[:229]]
    matrix = np.zeros((4, 230), dtype=np.uint8)
    matrix[0, 0] = matrix[1, 0] = matrix[2, 1] = matrix[3, 2] = 1
    original = matrix.copy()
    result = impact_preview(["a", "b", "c", "d"], matrix, ["topcv", "topcv", "itviec", "itviec"], items, {"b", "d"})
    assert result["ninput_p4"] == 4 and result["ncohort_proposed"] == 2 and result["nexcluded_proposed"] == 2
    assert result["autocad_jobs"] == {"before": 2, "after": 1}
    assert result["new_zero_columns"] == [items[2]["column"]]
    assert result["columns_unchanged"] and result["skill_width"] == 230
    assert not result["decisions_approved"] and not result["canonical_artifacts_modified"]
    np.testing.assert_array_equal(matrix, original)


def test_impact_rejects_unknown_ids_and_wrong_width():
    with pytest.raises(ValueError, match="known explicit"):
        impact_preview(["a"], np.zeros((1, 230)), ["topcv"], [], {"unknown"})
    with pytest.raises(ValueError, match="230"):
        impact_preview(["a"], np.zeros((1, 229)), ["topcv"], [], set())
