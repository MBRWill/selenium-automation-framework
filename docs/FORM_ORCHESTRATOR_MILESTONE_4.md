# Form Orchestrator Milestone 4: offline page processing

Milestone 4 connects the pure extraction, resolution, writing, validation, and
repair components into `FormOrchestrator.process_page()`. It remains an offline
domain service: controls are supplied by a caller, and the result contains no
live elements or page-level actions.

## Complete offline pipeline

For every supplied control, the orchestrator performs:

```text
FieldExtractor
-> AnswerResolver
-> FieldWriter
-> current validation collection
-> bounded AnswerResolver.repair() for invalid fields only
-> repaired FieldWriter call
-> fresh extraction and verification
-> deduplicated ReviewRecord collection
-> FormPageResult
```

Resolution retains the confirmed priority: valid LinkedIn value, verified
profile fact or preset, trusted policy, ordinary answer provider, eligible
reviewed fallback, then unresolved only when answering is unsafe or
type-impossible. A failure on one field is converted into a safe field result;
processing continues for the remaining controls.

## Application-scoped completion cache

Completed valid fields are cached within one active application. The cache key
uses the stable extractor field identity plus a SHA-256 semantic signature over
question, kind, visible options, constraints, validation message, current
value, and application/job context. It never uses Python's process-dependent
`hash()`.

An unchanged cached field does not call the answer provider, writer, or review
sink again. Relevant DOM or semantic changes invalidate reuse. Changing the
application or job identity clears the completion cache.

## Bounded repair and continuity

Only fields with current validation issues enter repair. Valid fields are not
re-resolved or rewritten. The default repair budget is two rounds:

1. deterministic type, length, range, step, and visible-option repair;
2. provider repair with the actual browser message and constraints, followed
   by an eligible ordinary fallback when policy permits it.

Each repaired answer is written, freshly extracted, and validated again.
There is no unbounded loop. An ordinary initial validation failure remains
repairable and does not imply application discard. Low-confidence usable
ordinary answers remain resolved with later review required.

## Review-record boundary

`ReviewSink.record()` is an offline protocol. `InMemoryReviewSink` provides
deterministic SHA-256 deduplication by application, job, field, source, and
final answer. Only the final verified provider/default answer, or another
answer explicitly marked for review, is recorded. Preserved LinkedIn values,
verified profile facts, and trusted policy answers are not recorded by default.

The orchestrator never opens or writes a review file. Runtime CSV/Excel
persistence remains deferred to a later adapter.

## Page statuses

- `READY_FOR_NAVIGATION`: every required field is verified and no required
  protected or type-impossible field remains.
- `RETRY_REQUIRED`: a required ordinary control is temporarily unavailable or
  otherwise retryable without page-level action.
- `BLOCKED_PROTECTED_FACT`: a required exact fact is unavailable or cannot map
  to the live control.
- `BLOCKED_TYPE_IMPOSSIBLE`: no type-valid value can satisfy a required field.
- `FAILED`: a required field encountered a contained processing failure or an
  ordinary repair budget was exhausted.

Optional invalid fields remain visible in diagnostics but do not necessarily
block the page result.

## Protected facts and containment

Work authorization, sponsorship, citizenship/EU citizenship, clearance,
education and certification possession, driving-licence possession, actual
employment history, legal declarations, and exact identity facts remain
exact-only. Verified profile data may correct a conflicting value. Provider
answers and ordinary Yes/Sí defaults never fill a missing protected fact.

Extraction, resolution, writing, re-extraction, repair, and review-sink
failures are contained with safe reason codes. Result representations expose
counts and identities rather than long answers, raw markup, exception text,
credentials, or private profile data.

## Deferred browser flow

Future browser integration may use the result as follows:

```text
collect current controls
-> process_page()
-> if READY_FOR_NAVIGATION, browser layer may advance
-> if the page reports validation errors, convert them to ValidationIssue
-> process only invalid fields again
-> never discard solely because an ordinary field initially failed
```

This milestone does not integrate with the runtime script, operate browser
navigation, manage page or window lifecycle, persist review files, or perform
a real provider request.
