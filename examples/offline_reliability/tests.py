# Copyright 2026 jojo
# SPDX-License-Identifier: Apache-2.0
"""Synthetic contract tests; no engine dependencies, credentials, or network."""

from dataclasses import replace
from datetime import date
from decimal import Decimal, Inexact, ROUND_UP, localcontext
import json
import socket
import unittest
from unittest.mock import patch

from .issues import build_registry, classify, issue_id
from .metrics import Flow, comparable_ratio
from .replay import FIXTURE, replay
from .usage import Usage, observe, summarize


class IssueTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"note-b": ["  Missing definition.\n"], "note-a": [
            "  Missing definition.\n", "Missing date."
        ]}
        self.registry = build_registry("synthetic-review", self.sources)
        self.rows = [{"issue_id": item.id, "label": "open"} for item in self.registry]

    def test_deduplication_preserves_exact_text_and_all_sources(self):
        result = classify(self.registry, self.rows, frozenset({"open"}))
        issue = next(row.issue for row in result if row.issue.text.startswith("  "))
        self.assertEqual(issue.text, "  Missing definition.\n")
        self.assertEqual([(s.name, s.index) for s in issue.sources], [("note-a", 0), ("note-b", 0)])
        self.assertEqual(len(result), 2)
        self.sources["note-a"][0] = "Later edit"
        self.assertEqual(issue.text, "  Missing definition.\n")

    def test_identity_scope_exact_text_and_unambiguous_boundaries(self):
        self.assertNotEqual(issue_id("a", "text"), issue_id("b", "text"))
        self.assertNotEqual(issue_id("a", "text"), issue_id("a", " text"))
        self.assertNotEqual(issue_id("a", "é"), issue_id("a", "e\u0301"))
        self.assertNotEqual(issue_id("a\0b", "c"), issue_id("a", "b\0c"))

    def test_registry_and_judgment_order_do_not_change_result(self):
        self.assertEqual(self.registry, build_registry(
            "synthetic-review", dict(reversed(list(self.sources.items())))
        ))
        self.assertEqual(
            classify(self.registry, self.rows, frozenset({"open"})),
            classify(self.registry, list(reversed(self.rows)), frozenset({"open"})),
        )

    def test_loss_invention_duplication_and_rewriting_are_rejected(self):
        invalid = [
            self.rows[:-1], self.rows + self.rows[:1],
            self.rows + [{"issue_id": "invented", "label": "open"}],
            [dict(self.rows[0], text="rewritten")] + self.rows[1:],
            [dict(self.rows[0], label="unsupported")] + self.rows[1:],
            [dict(self.rows[0], issue_id=[])] + self.rows[1:],
            [dict(self.rows[0], label=[])] + self.rows[1:],
        ]
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                classify(self.registry, rows, frozenset({"open"}))

    def test_repeated_occurrences_are_all_preserved(self):
        registry = build_registry("scope", {"source": ["same", "same"]})
        self.assertEqual(len(registry), 1)
        self.assertEqual([source.index for source in registry[0].sources], [0, 1])

    def test_invalid_source_shapes_and_blank_text(self):
        for sources in ([], {"source": "not a list"}, {"source": [" "]}, {"": ["ok"]}):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                build_registry("scope", sources)

    def test_empty_registry_and_duplicate_registry(self):
        self.assertEqual(classify((), [], frozenset({"open"})), ())
        with self.assertRaises(ValueError):
            classify(self.registry * 2, self.rows, frozenset({"open"}))

    def test_label_policy_must_be_an_explicit_nonempty_set(self):
        for labels in ("open", frozenset(), frozenset({""}), frozenset({None})):
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                classify(self.registry, self.rows, labels)


class UsageTests(unittest.TestCase):
    def test_stale_response_never_leaks_into_new_attempt(self):
        old = observe("one", "one", {"total_tokens": 12})
        new = observe("two", "one", {"total_tokens": 12})
        self.assertEqual(old.total_tokens, 12)
        self.assertIsNone(new.total_tokens)
        self.assertIsNone(observe("three").total_tokens)

    def test_unknown_is_not_zero_and_missing_total_is_not_inferred(self):
        rows = [observe("one", "one", {"input_tokens": 4, "output_tokens": 2}),
                observe("two", "two", {"input_tokens": 0}), observe("three")]
        summary = summarize(rows)
        field = summary["fields"]["input_tokens"]
        self.assertEqual(field, {"known_subtotal": 4, "known_attempts": 2,
                                 "unknown_attempts": 1, "all_attempts_total": None})
        self.assertIsNone(rows[0].total_tokens)
        self.assertIsNone(summary["billed_cost"])
        self.assertEqual(summarize([])["fields"]["total_tokens"]["all_attempts_total"], 0)

    def test_invalid_counts_remain_unknown(self):
        for value in (-1, True, False, 3.5, "3", float("nan"), {}):
            with self.subTest(value=value):
                self.assertIsNone(observe("a", "a", {"input_tokens": value}).input_tokens)
        self.assertIsNone(observe("a", "a", []).input_tokens)
        with self.assertRaises(ValueError):
            Usage("a", input_tokens=True)


    def test_complete_totals_include_explicit_zero(self):
        summary = summarize([observe("a", "a", {"total_tokens": 7}),
                             observe("b", "b", {"total_tokens": 0})])
        self.assertEqual(summary["fields"]["total_tokens"], {
            "known_subtotal": 7, "known_attempts": 2,
            "unknown_attempts": 0, "all_attempts_total": 7,
        })

    def test_same_attempt_cannot_be_counted_twice(self):
        with self.assertRaises(ValueError):
            summarize([observe("same"), observe("same")])
        with self.assertRaises(ValueError):
            observe("")

    def test_observation_is_detached_from_adapter_mutation(self):
        counters = {"total_tokens": 9}
        observation = observe("one", "one", counters)
        counters["total_tokens"] = 100
        self.assertEqual(observation.total_tokens, 9)


class MetricTests(unittest.TestCase):
    def setUp(self):
        self.flow = Flow(Decimal("30"), "millions", "SYN", "reported",
                         "Example Workshop", date(2024, 1, 1), date(2024, 3, 31), "synthetic-a")
        self.denominator = replace(self.flow, value=Decimal("120"), evidence_id="synthetic-b")

    def test_ratio_retains_evidence_ids(self):
        ratio = comparable_ratio(self.flow, self.denominator)
        self.assertEqual(ratio.value, Decimal("0.25"))
        self.assertEqual(ratio.evidence_ids, ("synthetic-a", "synthetic-b"))


    def test_ratio_is_independent_of_callers_decimal_context(self):
        numerator = replace(self.flow, value=Decimal("1"))
        denominator = replace(self.denominator, value=Decimal("3"))
        expected = comparable_ratio(numerator, denominator)
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_UP
            context.traps[Inexact] = True
            self.assertEqual(comparable_ratio(numerator, denominator), expected)
        self.assertEqual(expected.value, Decimal("0.3333333333333333333333333333"))

    def test_every_comparability_dimension_is_enforced(self):
        mutations = {"unit": "units", "currency": "OTHER", "basis": "forecast",
                     "scope": "Different Workshop", "start": date(2024, 2, 1),
                     "end": date(2024, 6, 30)}
        for field, value in mutations.items():
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                comparable_ratio(self.flow, replace(self.denominator, **{field: value}))

    def test_bad_values_dates_and_missing_metadata(self):
        for value in (Decimal("NaN"), Decimal("Infinity"), 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                replace(self.flow, value=value)
        for mutation in ({"start": date(2025, 1, 1)}, {"start": "2024-01-01"},
                         {"currency": ""}, {"evidence_id": " "}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                replace(self.flow, **mutation)
        with self.assertRaisesRegex(ValueError, "zero"):
            comparable_ratio(self.flow, replace(self.denominator, value=Decimal(0)))


class ReplayTests(unittest.TestCase):
    def test_frozen_replay_and_negative_examples_without_network(self):
        raw = FIXTURE.read_bytes()
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")), \
                patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            first = replay(raw)
            self.assertEqual(first, replay(raw))
        self.assertEqual(first["ratio"]["value"], "0.25")
        self.assertEqual(first["rejected_examples"], ["missing_issue", "different_unit"])
        self.assertEqual(first["usage"]["fields"]["total_tokens"]["unknown_attempts"], 2)
        self.assertIsNone(first["usage"]["fields"]["total_tokens"]["all_attempts_total"])
        self.assertNotEqual(first["fixture_sha256"], replay(raw + b"\n")["fixture_sha256"])

    def test_unsupported_snapshot_version_is_rejected(self):
        snapshot = json.loads(FIXTURE.read_bytes())
        snapshot["schema_version"] = 2
        with self.assertRaises(ValueError):
            replay(json.dumps(snapshot).encode())


if __name__ == "__main__":
    unittest.main()
