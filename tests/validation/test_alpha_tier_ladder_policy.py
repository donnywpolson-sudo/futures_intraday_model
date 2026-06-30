from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "configs" / "alpha_tiered.yaml"

RESEARCH_YEARS = {
    "tier_1_research": [2023, 2024],
    "tier_2_research": [2018, 2019, 2020, 2021, 2022, 2023, 2024],
    "tier_3_research": [
        2010,
        2011,
        2012,
        2013,
        2014,
        2015,
        2016,
        2017,
        2018,
        2019,
        2020,
        2021,
        2022,
        2023,
        2024,
    ],
}

HOLDOUT_PROFILES = ("tier_1_holdout", "tier_2_holdout", "tier_3_holdout")
FORWARD_PROFILES = ("tier_1_forward", "tier_2_forward", "tier_3_forward")


def _load_config() -> dict[str, object]:
    payload = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict)
    return payload


def _profiles() -> dict[str, dict[str, object]]:
    profiles = _load_config()["profiles"]
    assert isinstance(profiles, dict)
    return profiles


def test_research_profiles_exclude_holdout_and_forward_years() -> None:
    profiles = _profiles()

    for profile_name, expected_years in RESEARCH_YEARS.items():
        profile = profiles[profile_name]
        assert profile["years"] == expected_years
        assert 2025 not in expected_years
        assert 2026 not in expected_years
        assert profile.get("forbid_research_use", False) is False


def test_holdout_and_forward_profiles_are_locked_out_of_research_use() -> None:
    profiles = _profiles()

    for profile_name in HOLDOUT_PROFILES:
        profile = profiles[profile_name]
        assert profile["years"] == [2025]
        assert profile["forbid_research_use"] is True
        assert str(profile["description"]).startswith("Locked Holdout:")

    for profile_name in FORWARD_PROFILES:
        profile = profiles[profile_name]
        assert profile["years"] == [2026]
        assert profile["forbid_research_use"] is True
        assert str(profile["description"]).startswith("Forward:")
        assert "current/partial year" in str(profile["description"])


def test_primary_aliases_resolve_to_research_profiles_only() -> None:
    aliases = _load_config()["aliases"]
    assert isinstance(aliases, dict)

    assert aliases["tier_1"] == "tier_1_research"
    assert aliases["tier_2"] == "tier_2_research"
    assert aliases["tier_3"] == "tier_3_research"
    assert aliases["tier_1_final_holdout"] == "tier_1_holdout"
    assert aliases["tier_2_final_holdout"] == "tier_2_holdout"
    assert aliases["tier_3_final_holdout"] == "tier_3_holdout"
    assert aliases["tier_1_forward_2026"] == "tier_1_forward"
    assert aliases["tier_2_forward_2026"] == "tier_2_forward"
    assert aliases["tier_3_forward_2026"] == "tier_3_forward"


def test_research_descriptions_are_plain_english_ladder_names() -> None:
    profiles = _profiles()

    assert str(profiles["tier_1_research"]["description"]).startswith("Core Research:")
    assert str(profiles["tier_2_research"]["description"]).startswith("Robustness Research:")
    assert str(profiles["tier_3_research"]["description"]).startswith("Stress Research:")
