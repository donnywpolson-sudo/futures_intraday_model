from __future__ import annotations

import json
from pathlib import Path

from scripts.validation import enforce_model_trust_gate as gate


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _closeout(tmp_path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "run_id": gate.DEFAULT_RUN_ID,
        "verdict": gate.CURRENT_LINE_CLOSED_VERDICT,
        "modeling_pause_required": True,
        "future_evidence_work_allowed": True,
        "future_modeling_allowed": False,
        "promotion_allowed": False,
        "non_approval": {
            "target_discovery": False,
            "source_tests": False,
            "wfa_modeling": False,
            "phase8_refresh": False,
            "promotion": False,
            "artifact_freeze": False,
            "final_holdout": False,
            "paper": False,
            "live": False,
            "provider_downloads": False,
            "cleanup": False,
            "staging_commit_push": False,
            "rescue_tuning": False,
        },
    }
    payload.update(overrides)
    return _write_json(tmp_path / "closeout.json", payload)


def _matrix(tmp_path: Path, *, ready: bool) -> Path:
    return _write_json(
        tmp_path / "matrix.json",
        {
            "run_id": gate.DEFAULT_RUN_ID,
            "alpha_evidence_ready": ready,
            "verdict": "READY" if ready else gate.PAUSE_MATRIX_VERDICT,
        },
    )


def test_closeout_blocks_wfa_modeling(tmp_path: Path) -> None:
    result = gate.enforce_model_trust_gate(
        repo_root=tmp_path,
        closeout_path=_closeout(tmp_path),
        matrix_path=_matrix(tmp_path, ready=False),
        intended_action="wfa-modeling",
    )

    assert result["allowed"] is False
    assert result["status"] == "BLOCKED_BY_MODEL_TRUST_GATE"
    assert "current model line is closed by alpha evidence closeout" in result["blockers"]
    assert "wfa-modeling is not approved by closeout non_approval policy" in result["blockers"]


def test_closeout_allows_evidence_work_only(tmp_path: Path) -> None:
    result = gate.enforce_model_trust_gate(
        repo_root=tmp_path,
        closeout_path=_closeout(tmp_path),
        matrix_path=_matrix(tmp_path, ready=False),
        intended_action="evidence-work",
    )

    assert result["allowed"] is True
    assert result["status"] == "ALLOW_EVIDENCE_WORK_ONLY"
    assert result["allowed_without_separate_approval"] == [
        "evidence-work",
        "predeclared-research-plan",
    ]


def test_missing_closeout_falls_back_to_matrix_and_blocks_modeling(tmp_path: Path) -> None:
    result = gate.enforce_model_trust_gate(
        repo_root=tmp_path,
        closeout_path=tmp_path / "missing_closeout.json",
        matrix_path=_matrix(tmp_path, ready=False),
        intended_action="phase8-refresh",
    )

    assert result["allowed"] is False
    assert result["evidence_source"] == "alpha_evidence_gap_matrix"
    assert "alpha evidence matrix is not ready" in result["blockers"]
    assert "phase8-refresh requires a passing closeout or separate bounded approval" in result["blockers"]


def test_clean_worktree_requirement_blocks_when_dirty_paths_exist(monkeypatch, tmp_path: Path) -> None:
    def fake_dirty_paths(repo_root: Path) -> tuple[list[str], str | None]:
        return [" M scripts/example.py"], None

    monkeypatch.setattr(gate, "_git_dirty_paths", fake_dirty_paths)

    result = gate.enforce_model_trust_gate(
        repo_root=tmp_path,
        closeout_path=_closeout(tmp_path),
        matrix_path=_matrix(tmp_path, ready=False),
        intended_action="predeclared-research-plan",
        require_clean_worktree=True,
    )

    assert result["allowed"] is False
    assert "worktree is dirty and --require-clean-worktree was set" in result["blockers"]
    assert result["repo"]["dirty"] is True


def test_cli_fail_on_blocked_returns_nonzero(tmp_path: Path, capsys) -> None:
    exit_code = gate.main(
        [
            "--repo-root",
            str(tmp_path),
            "--closeout",
            str(_closeout(tmp_path)),
            "--matrix",
            str(_matrix(tmp_path, ready=False)),
            "--intended-action",
            "promotion",
            "--fail-on-blocked",
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 1
    assert "BLOCKED_BY_MODEL_TRUST_GATE" in stdout
