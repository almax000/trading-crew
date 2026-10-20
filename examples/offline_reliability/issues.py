# Copyright 2026 jojo
# SPDX-License-Identifier: Apache-2.0
"""Keep source text outside model control; accept only complete ID classifications."""

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Dict, FrozenSet, List, Tuple


@dataclass(frozen=True)
class Source:
    name: str
    index: int


@dataclass(frozen=True)
class Issue:
    id: str
    scope: str
    text: str
    sources: Tuple[Source, ...]


@dataclass(frozen=True)
class ClassifiedIssue:
    issue: Issue
    label: str


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected nonblank text")


def issue_id(scope: str, text: str) -> str:
    """Exact text is identity: no trimming, case folding, or Unicode normalization.

    A JSON pair makes the boundary unambiguous even when text contains NUL.
    The hash identifies content; it is neither anonymization nor proof of truth.
    """
    _text(scope)
    _text(text)
    payload = json.dumps([scope, text], ensure_ascii=False, separators=(",", ":"))
    return "issue-" + sha256(payload.encode("utf-8")).hexdigest()


def build_registry(scope: str, sources: Dict[str, List[str]]) -> Tuple[Issue, ...]:
    """Merge identical text within one scope, retaining every source occurrence."""
    _text(scope)
    if type(sources) is not dict:
        raise ValueError("sources must be an object")
    for name, items in sources.items():
        _text(name)
        if type(items) is not list:
            raise ValueError("each source must contain a list")
        for text in items:
            _text(text)
    records = {}
    for name in sorted(sources):
        for index, text in enumerate(sources[name]):
            key = issue_id(scope, text)
            if key in records and records[key][0] != text:
                raise ValueError("content hash collision")
            records.setdefault(key, (text, []))[1].append(Source(name, index))
    return tuple(
        Issue(key, scope, text, tuple(origins))
        for key, (text, origins) in sorted(records.items())
    )


def classify(
    registry: Tuple[Issue, ...],
    judgments: List[dict],
    allowed_labels: FrozenSet[str],
) -> Tuple[ClassifiedIssue, ...]:
    """Reject missing, repeated, invented IDs and model-supplied source text.

    Labels are application policy, not evidence that an issue has been resolved.
    """
    if not isinstance(allowed_labels, (set, frozenset)) or not allowed_labels or any(
        not isinstance(label, str) or not label.strip() for label in allowed_labels
    ):
        raise ValueError("allowed_labels must contain nonblank strings")
    known = {item.id: item for item in registry}
    if len(known) != len(registry):
        raise ValueError("registry contains duplicate IDs")
    if type(judgments) is not list:
        raise ValueError("judgments must be a list")
    labels = {}
    for row in judgments:
        if type(row) is not dict or set(row) != {"issue_id", "label"}:
            raise ValueError("a judgment must contain only issue_id and label")
        key, label = row["issue_id"], row["label"]
        if not isinstance(key, str) or key not in known:
            raise ValueError("unknown issue ID")
        if key in labels:
            raise ValueError("duplicate issue ID")
        if not isinstance(label, str) or label not in allowed_labels:
            raise ValueError("unsupported label")
        labels[key] = label
    if set(labels) != set(known):
        raise ValueError("classification must cover every issue exactly once")
    return tuple(ClassifiedIssue(known[key], labels[key]) for key in sorted(known))
