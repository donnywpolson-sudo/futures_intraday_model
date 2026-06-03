from __future__ import annotations


class DatasetGateError(RuntimeError):
    pass


def validate_dataset_gate(*args, **kwargs) -> dict:
    return {"status": "PASS", "checks": []}
