"""Make ``backend/`` importable so tests can ``import ai`` / ``app`` / ``iot``."""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


import pytest


@pytest.fixture(autouse=True)
def _never_touch_the_real_llm_cache(tmp_path, monkeypatch):
    """Redirect the LLM answer cache to a temp file for EVERY test.

    Learned the hard way: any bridge test that posts an enrichment without `fallback=True`
    counts as a live answer and calls `remember()`, and the cache tests' cleanup called
    `clear()`, which unlinks the file. Between them the suite both polluted and deleted the real
    cache at backend/ai/data/llm_cache.json — once overwriting a warmed Gemini answer with
    `{"what": "x"}`, which would then have been replayed on stage as a "cached Gemini answer".
    """
    try:
        from ai import llm_cache
    except Exception:
        yield
        return
    monkeypatch.setattr(llm_cache, "CACHE_PATH", tmp_path / "llm_cache.json")
    llm_cache.reset_memory()
    yield
    llm_cache.reset_memory()
