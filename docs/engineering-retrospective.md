# Engineering retrospective

TradingCrew began as a multi-agent research prototype built on TradingAgents,
adding a web interface and support for additional markets. Later experiments
made the boundaries around model output more valuable than adding more agent
roles. This closing update preserves a few of those boundaries as standalone,
synthetic, offline examples.

Active feature development is paused because the maintainer's time is moving to
other projects. There is no commitment to ongoing model/provider compatibility,
market-data integration, hosted service availability or a release schedule.
The existing application remains available as historical research code.

## Preserve the input before evaluating the output

A model can return plausible JSON while quietly dropping an inconvenient issue.
The useful contract is stricter than valid JSON: the application holds the exact
source text and provenance, assigns stable IDs, then requires the response to
classify each ID exactly once. An omitted, invented or duplicate ID rejects the
whole mapping. A label does not itself resolve a problem; downstream decisions
still need policy and evidence.

The new registry demonstrates this contract with synthetic workshop notes. It
does not carry over portfolio rules, investment actions or an agent runtime.
Content hashes are identifiers, not anonymization or proof of authenticity.

## Unknown usage is an observation, not a zero

Adapters may expose metadata only for successful calls, or leave a previous
response attached to a reusable object. Summing that state can undercount missing
attempts or double-count an old response. Bind observations to unique attempt IDs,
preserve absent counters as unknown, and report both known subtotal and coverage.
Only report a complete total when every included attempt has that field.

This does not establish a bill. Retries can be charged without returning usage;
provider metadata may be partial or inconsistent. No fee or token total is
estimated in these examples, and a caller can still break the contract by tagging
stale metadata with the new ID.

## Reject incompatible arithmetic before asking for an explanation

A ratio can be perfectly calculated and conceptually wrong: different currencies,
unit scales, periods, entities or accounting bases can make inputs incomparable.
Require those attributes explicitly and reject mismatches before division. The
example deliberately implements only a same-period flow ratio; supporting growth
or valuation would need additional semantics.

Equal labels do not verify the underlying evidence. Humans or upstream data
validation must establish the source definitions and the meaning of the comparison.

## Make claims no broader than the verification

Frozen synthetic input makes regression tests repeatable. Negative cases test
whether the program refuses an invalid result, rather than only accepting a happy
path. A digest helps identify exactly which input bytes were replayed, but it
cannot prove that an input was available at a historical decision time.

Multiple agents using related models and the same evidence are not automatically
independent reviewers. Agreement, structured output and many passing tests are
not evidence of reliable financial judgment. Offline contract tests and real
model evaluation answer different questions.

This update validates only the new offline examples. It does not rerun paid LLM
calls, live market-data paths, the old web application or trading performance.
Provider/model lists and installation instructions below the status notices in
the legacy READMEs describe the earlier implementation, not current verification.

## What is retained

The update adds three small contracts, one frozen synthetic fixture, a replay demo,
and tests for their success and rejection paths. It keeps the public repository's
existing history, license and upstream notices. No private history, datasets,
account state or local operations configuration is imported.

The examples are intentionally separate from the legacy engine. They are useful
to read, run and adapt, without reviving a research product or promising a general
workflow framework.

[Run the offline examples](../examples/offline_reliability/README.md)
