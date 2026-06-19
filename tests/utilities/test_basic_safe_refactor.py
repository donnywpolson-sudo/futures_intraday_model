from __future__ import annotations

from pathlib import Path

from scripts.dev.basic_safe_refactor import UTF8_BOM, cleaned_text, refactor_file


def test_cleaned_text_strips_only_outside_string_literals() -> None:
    source = (
        "VALUE = 1  \n"
        'TEXT = """keep trailing spaces   \n'
        'inside string   \n'
        '"""  \n'
        "# comment  \n"
    )

    cleaned, changes, skipped = cleaned_text(Path("example.py"), source)

    assert skipped is None
    assert changes == ("strip trailing whitespace on 2 line(s)",)
    assert cleaned == (
        "VALUE = 1\n"
        'TEXT = """keep trailing spaces   \n'
        'inside string   \n'
        '"""  \n'
        "# comment\n"
    )


def test_refactor_file_requires_write_to_modify(tmp_path: Path) -> None:
    path = tmp_path / "example.py"
    path.write_text("VALUE = 1  ", encoding="utf-8")

    dry_run = refactor_file(path, write=False)

    assert dry_run.changed
    assert path.read_text(encoding="utf-8") == "VALUE = 1  "

    write_run = refactor_file(path, write=True)

    assert write_run.changed
    assert path.read_text(encoding="utf-8") == "VALUE = 1\n"


def test_refactor_file_cleans_bom_file_and_preserves_bom(tmp_path: Path) -> None:
    path = tmp_path / "example.py"
    path.write_bytes(UTF8_BOM + b"VALUE = 1  ")

    write_run = refactor_file(path, write=True)
    raw = path.read_bytes()

    assert write_run.changed
    assert raw.startswith(UTF8_BOM)
    assert raw.count(UTF8_BOM) == 1
    assert raw == UTF8_BOM + b"VALUE = 1\n"


def test_refactor_file_bom_dry_run_does_not_modify_bytes(tmp_path: Path) -> None:
    path = tmp_path / "example.py"
    original = UTF8_BOM + b"VALUE = 1  "
    path.write_bytes(original)

    dry_run = refactor_file(path, write=False)

    assert dry_run.changed
    assert path.read_bytes() == original
