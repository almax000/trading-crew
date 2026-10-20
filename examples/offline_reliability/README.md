# Offline reliability examples

Small, dependency-free examples of contracts around automated research. They are
independent of the legacy TradingCrew engine and do not connect to an LLM, market
data service, account, or trading system. Python 3.9+ is sufficient.

From the repository root:

```bash
python3 -m examples.offline_reliability
python3 -m unittest examples.offline_reliability.tests -v
```

No dependency installation or `.env` file is needed. The demo reads only its
bundled synthetic JSON fixture and prints JSON to stdout; it does not write files.
Do not run the legacy root `test.py` as part of these offline checks.

## What the examples preserve

| File | Contract | Negative cases |
| --- | --- | --- |
| `issues.py` | Stable IDs from exact text and scope; preserve all source occurrences; require one classification per ID | Missing, duplicate, invented IDs; rewritten text; unsupported labels |
| `usage.py` | Bind counters to a unique attempt; unknown counters remain `None`; distinguish subtotal from complete total | Stale response, missing/invalid counters, repeated attempt IDs |
| `metrics.py` | Divide two same-period flows only when unit, currency, basis, scope and dates match | Unit/currency/basis/scope/period mismatch; nonfinite value; zero denominator |
| `replay.py` | Replay frozen input bytes and report their SHA-256 | Missing issue and mixed units are explicitly rejected |

The fixture describes an imaginary workshop, with invented counts, evidence IDs
and a fictional currency `SYN`. Its two flow values produce `0.25`. Of three
attempts, one reports 13 total tokens, one has no metadata, and one carries a stale
response. Consequently the known subtotal is 13, two attempts remain unknown,
and the complete total and billed cost are `null`.

The issue registry retains whitespace and Unicode exactly. Identical text within
one scope is grouped with all its source positions; different scopes or different
text produce different IDs. Semantically identical but differently phrased issues
are not merged. The classification response accepts only IDs and labels, so it
cannot replace the program's stored text.

Usage adapters must allocate a fresh attempt ID **before dispatch** and associate
the actual response with that ID. Passing the current ID alongside stale counters
defeats the check. These examples preserve observations; they cannot authenticate
a provider response, discover unreported calls, reconcile a bill, or infer that a
failed call was free. Missing totals are not reconstructed from input/output counts.

The ratio accepts `Decimal` values and exact metadata labels. It does no currency,
scale or calendar conversion. It is intentionally limited to same-period flows,
such as operating surplus divided by sales. Growth, valuation, trailing/forward
comparison and stock/flow ratios need different contracts. Even matching labels
do not prove truthful source data or economically meaningful definitions.

The replay digest identifies the exact input bytes, including whitespace. It does
not prove origin, publication date, freshness, or absence of future information.
The replay entry point demonstrates one bundled schema; it is not a hardened
parser for arbitrary external files. Keep the fixture frozen to compare runs.

## Scope and provenance

These are newly written examples of lessons from later research prototypes.
They have no runtime dependency on those prototypes and include no private
histories, account records, research documents, prompts or captured model outputs.
All fixtures and expected results were created specifically for these examples.
They are provided under the repository's Apache-2.0 license, with the existing
TradingAgents attribution retained at the repository root.

Passing these tests establishes the stated local contracts. It does not establish
model judgment quality, independence between agents, profitable trading, or
end-to-end correctness of the legacy application. This is a reference example,
not a new maintained framework or a published package.

[Engineering retrospective](../../docs/engineering-retrospective.md)

[开发复盘（中文）](../../docs/engineering-retrospective-zh.md)
