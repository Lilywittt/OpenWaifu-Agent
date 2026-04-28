from __future__ import annotations

from typing import Any


def validate_contract_shape(payload: Any, contract: Any, label: str = "payload") -> None:
    if isinstance(contract, dict):
        if not isinstance(payload, dict):
            raise RuntimeError(f"{label} must be an object.")
        expected_keys = set(contract.keys())
        actual_keys = set(payload.keys())
        missing = sorted(expected_keys - actual_keys)
        if missing:
            raise RuntimeError(f"{label} is missing required keys: {', '.join(missing)}")
        for key, value in contract.items():
            validate_contract_shape(payload.get(key), value, f"{label}.{key}")
        return

    if isinstance(contract, list):
        if not isinstance(payload, list):
            raise RuntimeError(f"{label} must be a list.")
        if contract:
            for index, item in enumerate(payload):
                validate_contract_shape(item, contract[0], f"{label}[{index}]")
        return

    if isinstance(contract, str):
        if not isinstance(payload, str):
            raise RuntimeError(f"{label} must be a string.")
        return

    if isinstance(contract, bool):
        if not isinstance(payload, bool):
            raise RuntimeError(f"{label} must be a boolean.")
        return

    if isinstance(contract, int) and not isinstance(contract, bool):
        if not isinstance(payload, int) or isinstance(payload, bool):
            raise RuntimeError(f"{label} must be an integer.")
        return

    if isinstance(contract, float):
        if not isinstance(payload, (int, float)) or isinstance(payload, bool):
            raise RuntimeError(f"{label} must be a number.")
        return
