"""Skill wiring placeholder.

Teacher custom-skill CRUD/import flow has been removed by design.
"""
from __future__ import annotations

from . import get_app_core as _app_core

__all__: list[str] = []


def app_core_accessor(core=None):
    return _app_core(core)
