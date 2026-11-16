# -*- coding: utf-8 -*-
"""Bước 12_e5: embedding bullet, cache theo sha1(text), vector JD (trung bình mọi bullet + theo 3 section). Model giả, không mạng."""

import hashlib

import numpy as np
import pandas as pd

from processing.extraction.embed import embed_texts, job_vectors, load_cache


def fake_encoder(calls):
    def enc(texts):
        calls.append(list(texts))
        out = []
        for t in texts:
            h = hashlib.sha1(t.encode()).digest()
            v = np.frombuffer(h[:8], dtype=np.uint8).astype(np.float32) + 1.0
            out.append(v / np.linalg.norm(v))
        return np.vstack(out)
    return enc


def test_embed_texts_shape_norm_and_dedup(tmp_path):
    calls = []
    texts = ["a", "b", "a", "c", "b"]
    emb = embed_texts(texts, fake_encoder(calls), tmp_path, chunk=2)
    assert emb.shape == (5, 8) and np.allclose(np.linalg.norm(emb.astype(np.float32), axis=1), 1.0, atol=1e-2)
    assert np.allclose(emb[0], emb[2]) and np.allclose(emb[1], emb[4])
    assert sum(len(c) for c in calls) == 3  # chỉ a, b, c được tính một lần


def test_cache_hit_does_not_call_model_and_is_reproducible(tmp_path):
    calls = []
    first = embed_texts(["x", "y"], fake_encoder(calls), tmp_path, chunk=1)
    n = len(calls)
    calls2 = []
    second = embed_texts(["y", "x", "z"], fake_encoder(calls2), tmp_path, chunk=1)
    assert sum(len(c) for c in calls2) == 1  # chỉ z mới
    assert np.array_equal(second[0], first[1]) and np.array_equal(second[1], first[0])
    assert len(load_cache(tmp_path)) == 3 and n == 2


def test_job_vectors_all_and_per_section():
    idx = pd.DataFrame({"job_id_global": ["j1", "j1", "j1", "j2"],
                        "section": ["mo_ta", "yeu_cau", "yeu_cau", "mo_ta"]})
    emb = np.array([[1, 0], [0, 1], [0, 1], [1, 1]], dtype=np.float32)
    emb[3] /= np.linalg.norm(emb[3])
    ids = ["j1", "j2", "j3"]  # j3 không có bullet nào
    v = job_vectors(idx, emb, ids)
    assert v["all"].shape == (3, 2)
    assert np.allclose(np.linalg.norm(v["all"][:2], axis=1), 1.0)
    assert np.allclose(v["all"][2], 0)  # không có bullet: vector 0, không bịa
    assert np.allclose(v["yeu_cau"][0], [0, 1]) and np.allclose(v["phuc_loi"][0], 0)
    assert v["has"].tolist() == [[True, True, False], [True, False, False], [False, False, False]]  # mo_ta, yeu_cau, phuc_loi
