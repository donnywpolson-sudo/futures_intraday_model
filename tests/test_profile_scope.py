import pytest

from scripts.profile_scope import resolve_profile_name


def test_resolve_profile_name_allows_identity_alias() -> None:
    assert resolve_profile_name("all_raw", {"all_raw": "all_raw"}) == "all_raw"


def test_resolve_profile_name_rejects_real_alias_cycle() -> None:
    with pytest.raises(SystemExit, match="Profile alias cycle detected"):
        resolve_profile_name("a", {"a": "b", "b": "a"})
