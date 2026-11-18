"""Tests for scripts/capture_metar.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "capture_metar.py"


@pytest.fixture(scope="module")
def capture_module():
    spec = importlib.util.spec_from_file_location("capture_metar", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_metar"] = module
    spec.loader.exec_module(module)
    return module


def test_main_help_and_parser(capture_module) -> None:
    with pytest.raises(SystemExit) as exc:
        capture_module.main(["--help"])
    assert exc.value.code == 0


def test_main_upload_missing_env(capture_module, monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)

    with patch.object(
        capture_module,
        "capture_metar_observations",
        return_value=tmp_path / "2026-11-18.parquet",
    ):
        code = capture_module.main(["--upload"])
        assert code == 2


def test_upload_to_hf_skips_existing(capture_module, monkeypatch, tmp_path: Path) -> None:
    import types

    p = tmp_path / "2026-11-18.parquet"
    p.write_bytes(b"dummy")

    mock_api = MagicMock()
    mock_api.file_exists.return_value = True
    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.HfApi = MagicMock(return_value=mock_api)
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    uploaded = capture_module.upload_to_hf(p, "repo/id", "token", replace=False)
    assert uploaded is False
    mock_api.upload_file.assert_not_called()
