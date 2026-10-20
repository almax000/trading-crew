# Copyright 2026 jojo
# SPDX-License-Identifier: Apache-2.0
"""Replay one bundled synthetic snapshot without importing any model adapter."""

from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

from .issues import build_registry, classify
from .metrics import Flow, comparable_ratio
from .usage import observe, summarize

FIXTURE = Path(__file__).with_name("synthetic_snapshot.json")


def replay(raw: bytes) -> dict:
    snapshot = json.loads(raw)
    if snapshot["schema_version"] != 1:
        raise ValueError("unsupported snapshot version")
    registry = build_registry(snapshot["scope"], snapshot["sources"])
    classified = classify(
        registry, snapshot["judgments"], frozenset({"needs_evidence", "needs_review"})
    )
    usage = summarize(
        observe(row["attempt_id"], row.get("response_attempt_id"), row.get("counters"))
        for row in snapshot["attempts"]
    )
    flows = []
    for row in snapshot["flows"]:
        flows.append(Flow(
            value=Decimal(row["value"]), unit=row["unit"], currency=row["currency"],
            basis=row["basis"], scope=row["scope"],
            start=date.fromisoformat(row["start"]), end=date.fromisoformat(row["end"]),
            evidence_id=row["evidence_id"],
        ))
    if len(flows) != 2:
        raise ValueError("the example needs exactly two flows")
    ratio = comparable_ratio(*flows)
    rejected = []
    for name, operation in (
        ("missing_issue", lambda: classify(
            registry, snapshot["judgments"][:-1], frozenset({"needs_evidence", "needs_review"})
        )),
        ("different_unit", lambda: comparable_ratio(flows[0], replace(flows[1], unit="units"))),
    ):
        try:
            operation()
        except ValueError:
            rejected.append(name)
        else:
            raise AssertionError("negative example unexpectedly accepted: " + name)
    return {
        "fixture_sha256": sha256(raw).hexdigest(),
        "synthetic": True,
        "issues": [asdict(row) for row in classified],
        "usage": usage,
        "ratio": {"value": str(ratio.value), "evidence_ids": ratio.evidence_ids},
        "rejected_examples": rejected,
    }


def main() -> None:
    print(json.dumps(replay(FIXTURE.read_bytes()), ensure_ascii=False, indent=2, sort_keys=True))
