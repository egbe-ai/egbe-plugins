"""Shared project-relative artifact paths, copied into standalone skill bundles.

IDs select explicit work, never the newest directory. The defaults are stable
names for the first study/plan; callers set another ID for independent work.
"""
import os
import re


def artifact_path(value: str) -> str:
    for prefix, variable, default in (
        ("egbe-docs/research/", "EGBE_RESEARCH_ID", "market"),
        ("egbe-docs/marketing/plans/", "EGBE_GTM_PLAN_ID", "launch"),
    ):
        token = prefix + default
        if token not in value:
            continue
        identifier = os.environ.get(variable, default)
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,95}", identifier):
            raise ValueError(f"{variable} must be a lowercase work ID (letters, digits, - or _)")
        value = value.replace(token + "/", prefix + identifier + "/")
        if value == token:
            value = prefix + identifier
    return value
