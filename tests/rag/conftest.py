"""
Salida por consola del score de cada caso golden (solo con RUN_RAG_GOLDEN=1).
Sin esto los logs sólo aparecen usando ``pytest --log-cli-level=INFO``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import pytest

from tests.rag.golden_semantic_report import clear_records, write_summary_txt

_REPO_ROOT_FOR_HOOKS = Path(__file__).resolve().parents[2]

_HANDLER_TAG = "_rag_golden_stream_marker"


def pytest_sessionstart(session: pytest.Session) -> None:
    if os.environ.get("RUN_RAG_GOLDEN", "").strip() == "1":
        clear_records()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    if os.environ.get("RUN_RAG_GOLDEN", "").strip() != "1":
        return
    path = write_summary_txt(repo_root=_REPO_ROOT_FOR_HOOKS)
    if path:
        print(f"\n[golden_similarity] resumen TXT: {path}", flush=True)


@pytest.fixture(autouse=True)
def _live_golden_semantic_logs(request: pytest.FixtureRequest):
    nodeid = request.node.nodeid
    if "test_golden_semantic_similarity" not in nodeid:
        yield
        return

    if os.environ.get("RUN_RAG_GOLDEN", "").strip() != "1":
        yield
        return

    lg = logging.getLogger("rag_golden_semantic")
    if any(getattr(h, _HANDLER_TAG, False) for h in lg.handlers):
        yield
        return

    h = logging.StreamHandler()
    h.setLevel(logging.INFO)
    h.setFormatter(logging.Formatter("%(message)s"))
    setattr(h, _HANDLER_TAG, True)
    lg.addHandler(h)
    lg.setLevel(logging.INFO)
    old_propagate = lg.propagate
    lg.propagate = False

    yield

    lg.removeHandler(h)
    lg.handlers = [x for x in lg.handlers if not getattr(x, _HANDLER_TAG, False)]
    lg.propagate = old_propagate
