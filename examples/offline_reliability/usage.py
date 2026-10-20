# Copyright 2026 jojo
# SPDX-License-Identifier: Apache-2.0
"""Immutable per-attempt observations, with explicit gaps in provider metadata."""

from dataclasses import dataclass, fields
from typing import Iterable, Optional

@dataclass(frozen=True)
class Usage:
    attempt_id: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None

    def __post_init__(self):
        if not isinstance(self.attempt_id, str) or not self.attempt_id.strip():
            raise ValueError("attempt_id must be nonblank")
        for field in COUNTER_FIELDS:
            value = getattr(self, field)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("counts must be nonnegative integers or None")


# Keep the observation schema as the only definition of counter fields.
COUNTER_FIELDS = tuple(field.name for field in fields(Usage) if field.name != "attempt_id")


def observe(attempt_id: str, response_attempt_id=None, counters=None) -> Usage:
    """Bind a response to the attempt created by the caller before dispatch.

    Missing/stale responses yield unknown counters. Invalid individual counters
    also stay unknown. No totals or cached-token values are inferred.
    The adapter must bind response_attempt_id correctly; this is not attestation.
    """
    empty = Usage(attempt_id)
    if response_attempt_id != attempt_id or type(counters) is not dict:
        return empty
    values = {
        field: value if type(value) is int and value >= 0 else None
        for field in COUNTER_FIELDS
        for value in [counters.get(field)]
    }
    return Usage(attempt_id, **values)


def summarize(observations: Iterable[Usage]) -> dict:
    rows = tuple(observations)
    if len({row.attempt_id for row in rows}) != len(rows):
        raise ValueError("duplicate attempt IDs would double-count usage")
    summary = {}
    for field in COUNTER_FIELDS:
        known = [getattr(row, field) for row in rows if getattr(row, field) is not None]
        unknown = len(rows) - len(known)
        summary[field] = {
            "known_subtotal": sum(known),
            "known_attempts": len(known),
            "unknown_attempts": unknown,
            "all_attempts_total": None if unknown else sum(known),
        }
    return {
        "attempts": len(rows),
        "fields": summary,
        "billed_cost": None,
        "scope": "Observed counters only; neither a billing estimate nor a provider audit.",
    }
