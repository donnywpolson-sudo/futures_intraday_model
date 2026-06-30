from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


DEFAULT_PROFILE_CONFIG = Path("configs/alpha_tiered.yaml")


@dataclass(frozen=True)
class ProfileScope:
    requested_profile: str
    resolved_profile: str
    markets: list[str]
    years: list[int]

    @property
    def market_years(self) -> list[tuple[str, int]]:
        return [(market, year) for market in self.markets for year in self.years]


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_hash_or_missing(path: Path) -> str:
    return _file_sha256(path) if path.exists() else "MISSING"


def profile_config_hash(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.as_posix()):
        digest.update(_relative_path(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(_file_hash_or_missing(path).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def resolve_profile_name(profile: str, aliases: Mapping[str, Any]) -> str:
    resolved = profile
    seen: set[str] = set()
    while resolved in aliases:
        next_profile = str(aliases[resolved])
        if next_profile == resolved:
            break
        if resolved in seen:
            raise SystemExit(f"Profile alias cycle detected at {resolved!r}")
        seen.add(resolved)
        resolved = next_profile
    return resolved


def load_profile_scope(
    profile: str,
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    *,
    strict: bool = True,
) -> ProfileScope | None:
    config = _read_yaml(profile_config)
    aliases = config.get("aliases", {})
    if not isinstance(aliases, Mapping):
        aliases = {}
    resolved_profile = resolve_profile_name(profile, aliases)

    profiles = config.get("profiles", {})
    if not isinstance(profiles, Mapping) or resolved_profile not in profiles:
        if strict:
            known = sorted(str(key) for key in profiles) if isinstance(profiles, Mapping) else []
            raise SystemExit(f"Unknown profile {profile!r}. Known profiles: {', '.join(known)}")
        return None

    entry = profiles[resolved_profile]
    if not isinstance(entry, Mapping):
        if strict:
            raise SystemExit(f"Invalid profile config for {resolved_profile!r}")
        return None
    if bool(entry.get("discovery", False)):
        if strict:
            raise SystemExit(f"Discovery profile {resolved_profile!r} has no fixed scope")
        return None

    markets = entry.get("markets", [])
    years = entry.get("years", [])
    if not isinstance(markets, list) or not isinstance(years, list):
        if strict:
            raise SystemExit(f"Profile {resolved_profile!r} missing markets or years")
        return None

    return ProfileScope(
        requested_profile=profile,
        resolved_profile=resolved_profile,
        markets=[str(market) for market in markets],
        years=[int(year) for year in years],
    )


def scope_authority_metadata(
    *,
    profile: str,
    selected_market_years: Iterable[tuple[object, object]],
    profile_config: Path = DEFAULT_PROFILE_CONFIG,
    status: str | None = None,
    failure_count: int = 0,
    selected_input_count: int | None = None,
) -> dict[str, Any]:
    scope = load_profile_scope(profile, profile_config, strict=False)
    if scope is None or (profile != "tier_1" and scope.resolved_profile != "tier_1_research"):
        return {}

    actual = sorted({(str(market), int(year)) for market, year in selected_market_years})
    expected = sorted(scope.market_years)
    actual_set = set(actual)
    expected_set = set(expected)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    partial_scope = bool(missing or extra)
    authoritative = not partial_scope and int(failure_count) == 0

    return {
        "resolved_profile": scope.resolved_profile,
        "expected_markets": scope.markets,
        "expected_years": scope.years,
        "expected_input_count": len(expected),
        "selected_input_count": int(selected_input_count)
        if selected_input_count is not None
        else len(actual),
        "actual_input_count": len(actual),
        "partial_scope": partial_scope,
        "authoritative": authoritative,
        "missing_market_years": [
            {"market": market, "year": year} for market, year in missing
        ],
        "extra_market_years": [
            {"market": market, "year": year} for market, year in extra
        ],
    }
