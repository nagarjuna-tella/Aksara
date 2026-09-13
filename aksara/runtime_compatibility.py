"""Authoritative Python runtime compatibility policy for Aksara."""

from __future__ import annotations

from typing import Literal

MIN_SUPPORTED_PYTHON = (3, 11)
MAX_SUPPORTED_PYTHON = (3, 14)
SUPPORTED_PYTHON_LABEL = "3.11–3.14"

PythonSupportStatus = Literal["too_old", "supported", "too_new"]


def python_support_status(version: tuple[int, int]) -> PythonSupportStatus:
    """Classify a Python major/minor tuple against the release policy."""

    if version < MIN_SUPPORTED_PYTHON:
        return "too_old"
    if version > MAX_SUPPORTED_PYTHON:
        return "too_new"
    return "supported"
