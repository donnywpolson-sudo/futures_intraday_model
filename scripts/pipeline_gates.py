from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ManifestGateCheck:
    manifest: Mapping[str, Any] | None
    failures: list[str]
    evidence: dict[str, Any]

    @property
    def passed(self) -> bool:
        return not self.failures


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_path(value: object) -> Path:
    return Path(str(value)).expanduser().resolve()


def _paths_match(left: object, right: Path) -> bool:
    try:
        return _resolve_path(left) == right.expanduser().resolve()
    except (OSError, TypeError, ValueError):
        return False


def _read_json_manifest(path: Path) -> tuple[Mapping[str, Any] | None, list[str]]:
    if not path.exists():
        return None, [f"upstream manifest missing: {relative_path(path)}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"upstream manifest unreadable: {relative_path(path)}: {exc}"]
    if not isinstance(payload, Mapping):
        return None, [f"upstream manifest is not a JSON object: {relative_path(path)}"]
    return payload, []


def _matching_hash(hash_map: object, path: Path) -> str | None:
    if not isinstance(hash_map, Mapping):
        return None
    expected = path.expanduser().resolve()
    for raw_path, raw_hash in hash_map.items():
        try:
            if _resolve_path(raw_path) == expected:
                return str(raw_hash)
        except (OSError, TypeError, ValueError):
            continue
    return None


def _nonempty_sequence(value: object) -> bool:
    return isinstance(value, (list, tuple, set, dict)) and bool(value)


def _int_value(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item) for item in value]


def check_upstream_manifest(
    *,
    manifest_path: Path,
    expected_profile: str,
    expected_resolved_profile: str | None,
    expected_output_root: Path,
    expected_market_years: Iterable[tuple[str, int]],
    gate_name: str,
    expected_stage: str | None = None,
    block_warnings: bool = True,
    allowed_statuses: Iterable[str] = ("PASS",),
    accepted_warning_messages: Iterable[str] | None = None,
) -> ManifestGateCheck:
    failures: list[str] = []
    manifest, read_failures = _read_json_manifest(manifest_path)
    failures.extend(read_failures)
    expected_pairs = sorted({(str(market), int(year)) for market, year in expected_market_years})
    allowed_status_set = {str(status) for status in allowed_statuses}
    accepted_warning_set = (
        {str(message) for message in accepted_warning_messages}
        if accepted_warning_messages is not None
        else set()
    )

    evidence: dict[str, Any] = {
        "gate": gate_name,
        "status": "FAIL",
        "manifest_path": relative_path(manifest_path),
        "expected_profile": expected_profile,
        "expected_resolved_profile": expected_resolved_profile,
        "expected_output_root": relative_path(expected_output_root),
        "expected_market_year_count": len(expected_pairs),
        "allowed_statuses": sorted(allowed_status_set),
    }
    if manifest_path.exists():
        evidence["manifest_hash"] = file_sha256(manifest_path)

    if manifest is None:
        evidence["failures"] = failures
        return ManifestGateCheck(manifest=None, failures=failures, evidence=evidence)

    evidence["upstream_status"] = manifest.get("status")
    evidence["upstream_stage"] = manifest.get("stage")
    accepted_warnings_seen: list[str] = []

    def warning_failures(
        context: str,
        count_value: object,
        messages_value: object,
        *,
        require_messages: bool,
    ) -> None:
        warning_count_value = _int_value(count_value)
        messages = _string_sequence(messages_value)
        if block_warnings and messages:
            unaccepted = sorted({message for message in messages if message not in accepted_warning_set})
            if unaccepted:
                failures.append(f"{context} warnings are not accepted: {unaccepted}")
            else:
                accepted_warnings_seen.extend(messages)
        if not block_warnings or warning_count_value in (None, 0):
            return
        if accepted_warning_set and messages:
            return
        if accepted_warning_set and not require_messages:
            return
        failures.append(f"{context} warning_count is {warning_count_value}, not 0")

    if expected_stage is not None and manifest.get("stage") != expected_stage:
        failures.append(
            f"upstream manifest stage is {manifest.get('stage')!r}, not {expected_stage!r}"
        )
    if manifest.get("profile") != expected_profile:
        failures.append(
            f"upstream manifest profile is {manifest.get('profile')!r}, not {expected_profile!r}"
        )
    if expected_resolved_profile is not None:
        if manifest.get("resolved_profile") != expected_resolved_profile:
            failures.append(
                "upstream manifest resolved_profile is "
                f"{manifest.get('resolved_profile')!r}, not {expected_resolved_profile!r}"
            )
    if not _paths_match(manifest.get("output_root"), expected_output_root):
        failures.append(
            "upstream manifest output_root does not match current input root: "
            f"manifest={manifest.get('output_root')!r} current={relative_path(expected_output_root)}"
        )
    if manifest.get("status") not in allowed_status_set:
        failures.append(
            f"upstream manifest status is {manifest.get('status')!r}, not one of "
            f"{sorted(allowed_status_set)}"
        )

    failure_count = _int_value(manifest.get("failure_count"))
    if failure_count is None:
        failures.append("upstream manifest failure_count missing or invalid")
    elif failure_count != 0:
        failures.append(f"upstream manifest failure_count is {failure_count}, not 0")

    warning_failures(
        "upstream manifest",
        manifest.get("warning_count"),
        manifest.get("warnings"),
        require_messages=False,
    )

    summary = manifest.get("summary")
    if isinstance(summary, Mapping):
        fail_count = _int_value(summary.get("fail_count"))
        if fail_count not in (None, 0):
            failures.append(f"upstream manifest summary.fail_count is {fail_count}, not 0")
        warn_count = _int_value(summary.get("warn_count"))
        if block_warnings and warn_count not in (None, 0) and not accepted_warning_set:
            failures.append(f"upstream manifest summary.warn_count is {warn_count}, not 0")

    if _nonempty_sequence(manifest.get("failures")):
        failures.append("upstream manifest failures are non-empty")

    outputs = manifest.get("outputs")
    if isinstance(outputs, list):
        for index, output in enumerate(outputs):
            if not isinstance(output, Mapping):
                continue
            row_status = output.get("status")
            if row_status is not None and row_status not in allowed_status_set:
                failures.append(
                    f"upstream manifest output {index} status is {row_status!r}, "
                    f"not one of {sorted(allowed_status_set)}"
                )
            row_failure_count = _int_value(output.get("failure_count"))
            if row_failure_count not in (None, 0):
                failures.append(
                    f"upstream manifest output {index} failure_count is {row_failure_count}, not 0"
                )
            warning_failures(
                f"upstream manifest output {index}",
                output.get("warning_count"),
                output.get("warnings"),
                require_messages=True,
            )
            if _nonempty_sequence(output.get("failures")):
                failures.append(f"upstream manifest output {index} failures are non-empty")

    hash_map = manifest.get("output_file_hashes")
    for market, year in expected_pairs:
        output_path = expected_output_root / market / f"{year}.parquet"
        if not output_path.exists():
            failures.append(f"upstream output missing: {relative_path(output_path)}")
            continue
        expected_hash = _matching_hash(hash_map, output_path)
        if expected_hash is None:
            failures.append(f"upstream output hash missing: {relative_path(output_path)}")
            continue
        if expected_hash in {"", "MISSING", "NOT_WRITTEN"}:
            failures.append(
                f"upstream output hash invalid for {relative_path(output_path)}: {expected_hash}"
            )
            continue
        actual_hash = file_sha256(output_path)
        if actual_hash != expected_hash:
            failures.append(f"upstream output hash stale: {relative_path(output_path)}")

    evidence["status"] = "PASS" if not failures else "FAIL"
    evidence["accepted_warning_count"] = len(accepted_warnings_seen)
    evidence["accepted_warnings"] = sorted(set(accepted_warnings_seen))
    evidence["failures"] = failures
    return ManifestGateCheck(manifest=manifest, failures=failures, evidence=evidence)


def require_upstream_manifest(**kwargs: Any) -> ManifestGateCheck:
    check = check_upstream_manifest(**kwargs)
    if check.failures:
        joined = "; ".join(check.failures)
        raise SystemExit(f"{check.evidence['gate']} failed: {joined}")
    return check


def resolve_upstream_manifest_gate(
    *,
    manifest_arg: str | Path | None,
    default_manifest_path: Path,
    search_name: str,
    **check_kwargs: Any,
) -> ManifestGateCheck:
    if manifest_arg not in (None, "", "auto"):
        return require_upstream_manifest(manifest_path=Path(manifest_arg), **check_kwargs)

    candidates: list[Path] = []
    if default_manifest_path.exists():
        candidates.append(default_manifest_path)
    reports_root = Path("reports")
    if reports_root.exists():
        candidates.extend(
            sorted(
                reports_root.glob(f"**/{search_name}"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        )

    unique_candidates: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_candidates.append(candidate)

    failed_checks: list[ManifestGateCheck] = []
    for candidate in unique_candidates:
        check = check_upstream_manifest(manifest_path=candidate, **check_kwargs)
        if check.passed:
            check.evidence["auto_discovered"] = True
            check.evidence["candidate_count"] = len(unique_candidates)
            return check
        failed_checks.append(check)

    gate_name = str(check_kwargs.get("gate_name", "upstream_manifest_gate"))
    if not unique_candidates:
        raise SystemExit(
            f"{gate_name} failed: no upstream manifest candidates found for {search_name}"
        )
    first = failed_checks[0]
    joined = "; ".join(first.failures)
    raise SystemExit(
        f"{gate_name} failed: no PASS upstream manifest found among "
        f"{len(unique_candidates)} candidates; first candidate "
        f"{first.evidence['manifest_path']}: {joined}"
    )
