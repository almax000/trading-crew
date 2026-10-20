# Copyright 2026 jojo
# SPDX-License-Identifier: Apache-2.0
"""A deliberately narrow ratio: two same-period flows with matching metadata."""

from dataclasses import dataclass
from datetime import date
from decimal import Context, Decimal, localcontext
from typing import Tuple


@dataclass(frozen=True)
class Flow:
    value: Decimal
    unit: str
    currency: str
    basis: str
    scope: str
    start: date
    end: date
    evidence_id: str

    def __post_init__(self):
        if not isinstance(self.value, Decimal) or not self.value.is_finite():
            raise ValueError("value must be a finite Decimal")
        for name in ("unit", "currency", "basis", "scope", "evidence_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError("metadata must be nonblank")
        if type(self.start) is not date or type(self.end) is not date:
            raise ValueError("period boundaries must be dates")
        if self.start > self.end:
            raise ValueError("period start must not follow its end")


@dataclass(frozen=True)
class Ratio:
    value: Decimal
    evidence_ids: Tuple[str, str]


def comparable_ratio(numerator: Flow, denominator: Flow) -> Ratio:
    """No automatic currency, scale, accounting-basis, or period conversions.

    Matching labels are necessary, not sufficient: the caller must establish
    that both metrics have meaningful economic definitions and truthful metadata.
    This operation is not intended for growth, valuation, or stock/flow ratios.
    """
    for field in ("unit", "currency", "basis", "scope", "start", "end"):
        if getattr(numerator, field) != getattr(denominator, field):
            raise ValueError("incomparable " + field)
    if denominator.value == 0:
        raise ValueError("denominator must not be zero")
    with localcontext(Context(prec=28)):
        value = numerator.value / denominator.value
    return Ratio(value, (numerator.evidence_id, denominator.evidence_id))
