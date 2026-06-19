from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.databento_auth import (
    load_databento_api_key_from_file,
    normalize_api_key,
    resolve_databento_api_key,
)


def test_normalize_api_key_strips_wrapping_noise() -> None:
    assert normalize_api_key(None) == ""
    assert normalize_api_key("  db-test  ") == "db-test"
    assert normalize_api_key('"db-test"') == "db-test"
    assert normalize_api_key("'db-test'") == "db-test"


def test_load_databento_api_key_from_file_supports_env_assignment(tmp_path: Path) -> None:
    path = tmp_path / "databento.env"
    path.write_text(
        "# local ignored secret\nDATABENTO_API_KEY='db-file-test'\n",
        encoding="utf-8",
    )

    assert load_databento_api_key_from_file(path) == "db-file-test"


def test_load_databento_api_key_from_file_supports_raw_key(tmp_path: Path) -> None:
    path = tmp_path / "databento.env"
    path.write_text("  db-raw-test  \n", encoding="utf-8")

    assert load_databento_api_key_from_file(path) == "db-raw-test"


def test_resolve_databento_api_key_prefers_env_over_files(tmp_path: Path) -> None:
    key_file = tmp_path / "secrets" / "databento.env"
    key_file.parent.mkdir()
    key_file.write_text("DATABENTO_API_KEY=db-file-test\n", encoding="utf-8")

    assert (
        resolve_databento_api_key(
            env={"DATABENTO_API_KEY": "db-env-test"},
            key_files=[key_file],
        )
        == "db-env-test"
    )


def test_resolve_databento_api_key_reads_secrets_file_when_env_not_injected(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("DATABENTO_API_KEY", raising=False)
    key_file = tmp_path / "secrets" / "databento.env"
    key_file.parent.mkdir()
    key_file.write_text("DATABENTO_API_KEY=db-secrets-test\n", encoding="utf-8")

    assert resolve_databento_api_key(key_files=[key_file]) == "db-secrets-test"


def test_injected_empty_env_does_not_read_real_or_fake_files(tmp_path: Path) -> None:
    key_file = tmp_path / "secrets" / "databento.env"
    key_file.parent.mkdir()
    key_file.write_text("DATABENTO_API_KEY=db-file-test\n", encoding="utf-8")

    assert resolve_databento_api_key(env={}, key_files=[key_file]) == ""
