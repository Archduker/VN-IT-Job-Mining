# -*- coding: utf-8 -*-
"""Bao model VietAI/envit5-translation: GPU batch 4, tự lùi về CPU khi OOM. Chỉ import torch khi tạo đối tượng."""
from __future__ import annotations

from typing import Callable, List

from preprocessing.translation.core import GEN_PARAMS, MODEL_ID, MODEL_REVISION


class EnViTranslator:
    def __init__(self, batch_size: int = 4, device: str | None = None):
        import torch
        from huggingface_hub import hf_hub_download
        from transformers import AutoModelForSeq2SeqLM, PreTrainedTokenizerFast

        self.torch, self.batch_size = torch, batch_size
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        kw = {"revision": MODEL_REVISION}
        # AutoTokenizer lỗi với repo này trên transformers 5.22 (xem spike 10/11): nạp thẳng tokenizer.json
        try:
            tf = hf_hub_download(MODEL_ID, "tokenizer.json", local_files_only=True, **kw)
        except Exception:
            tf = hf_hub_download(MODEL_ID, "tokenizer.json", **kw)
        self.tok = PreTrainedTokenizerFast(tokenizer_file=tf, eos_token="</s>", pad_token="<pad>", unk_token="<unk>")
        try:
            self.model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, local_files_only=True, **kw)
        except Exception:
            self.model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, **kw)
        self.model.to(self.device).eval()
        self.peak_vram_mib = 0.0
        self.fell_back_to_cpu = False

    def count(self, text: str) -> int:
        return len(self.tok(text, add_special_tokens=False).input_ids)

    def _gen(self, batch: List[str]) -> List[str]:
        enc = self.tok([GEN_PARAMS["input_prefix"] + c for c in batch], return_tensors="pt", padding=True)
        enc.pop("token_type_ids", None)
        enc = {k: v.to(self.device) for k, v in enc.items()}
        with self.torch.no_grad():
            out = self.model.generate(**enc, do_sample=False, num_beams=GEN_PARAMS["num_beams"],
                                      max_new_tokens=GEN_PARAMS["max_new_tokens"])
        if self.device == "cuda":
            self.peak_vram_mib = max(self.peak_vram_mib, self.torch.cuda.max_memory_allocated() / 2**20)
        return self.tok.batch_decode(out, skip_special_tokens=True)

    def translate_batch(self, chunks: List[str]) -> List[str]:
        res: List[str] = []
        for i in range(0, len(chunks), self.batch_size):
            b = chunks[i:i + self.batch_size]
            try:
                res += self._gen(b)
            except self.torch.cuda.OutOfMemoryError:
                self.torch.cuda.empty_cache()
                self.model.to("cpu")
                self.device, self.fell_back_to_cpu = "cpu", True
                res += self._gen(b)
        return res

    def info(self) -> dict:
        import transformers
        return {"device": self.device, "batch_size": self.batch_size, "torch": self.torch.__version__,
                "transformers": transformers.__version__, "peak_vram_mib": round(self.peak_vram_mib),
                "fell_back_to_cpu": self.fell_back_to_cpu}


def make_context(batch_size: int = 4, cache_path=None):
    from preprocessing.translation.core import TranslationContext, load_approved_terms
    t = EnViTranslator(batch_size)
    ctx = TranslationContext(t.translate_batch, t.count, load_approved_terms(), cache_path, meta=t.info)
    ctx.translator = t
    return ctx
