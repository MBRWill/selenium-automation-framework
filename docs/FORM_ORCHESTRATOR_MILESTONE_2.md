# Form Orchestrator Milestone 2 contracts

Milestone 2 defines pure answer-resolution and validation-repair domain logic.
It has no Selenium dependency and does not implement browser navigation, modal
handling, Submit, window management, application counters, or pagination.

## Resolution contract

`AnswerResolver.resolve()` applies this order:

```text
valid value already present in LinkedIn
-> verified injected profile fact or preset
-> trusted deterministic policy
-> typed answer provider for an ordinary field
-> eligible ordinary Yes/Sí or constrained default
-> unresolved only when answering would be unsafe or type-impossible
```

Protected objective facts are the safety exception to blindly preserving a
pre-filled value: the resolver reconciles them against verified profile truth
and corrects a conflict. Missing or unverified protected facts are never sent
to AI and are never guessed.

`SemanticPolicy` centrally classifies English and Spanish questions. Its
categories keep work authorization, sponsorship, citizenship/EU citizenship,
clearance, certification possession, education possession, driving-licence
possession, employment history, criminal/legal declarations, exact salary,
and exact language level protected. Candidate possession questions are kept
distinct from statements about a job requirement. Ordinary experience,
capability, preference, commute, relocation, and travel questions may use the
provider. Optional marketing consent is deterministically declined, and a
required procedural acknowledgement is deterministically accepted only when
it is not a protected legal declaration.

Profile access is dependency-injected through `ProfileFactProvider`. The form
domain does not open a candidate-profile file or know how facts are stored.
Only `ProfileFactResult(found=True, verified=True, ...)` is accepted as profile
truth.

The typed `AnswerProvider` receives question, field kind, visible options,
constraints, non-protected candidate context, and (during repair) the actual
validation message and rejected value. It has no browser or navigation
capability. A usable low-confidence ordinary answer is accepted with
`requires_review=True`; provider uncertainty alone does not interrupt the
workflow.

## Future browser-orchestrator acceptance loop

The future browser adapter must use this exact workflow:

```text
click Next or Review
-> collect actual invalid fields
-> create one ValidationIssue per invalid field
-> repair those fields only
-> validate those fields again
-> retry navigation
-> do not discard the application merely because an ordinary field initially
   failed validation
```

Fields that are already valid are not passed back through resolution. A repair
request identifies exactly one field and carries the actual validation message,
rejected value, field kind, constraints, and current visible options.

## Bounded repair

`AnswerResolver.repair()` is application-session scoped:

1. Attempt 1 applies deterministic type, text-length, numeric min/max/step, and
   currently-visible-option repair.
2. If an ordinary field still fails, attempt 2 may call `AnswerProvider` with
   the actual validation context.
3. A final ordinary fallback may use a type-compatible constrained value.
   Yes/No fields may choose a visible Yes or Sí only when policy permits it.
4. Protected facts use verified profile data exclusively throughout repair.

`RETRY_REQUIRED` is non-terminal. The future browser adapter must keep the
application open, validate again, and submit the next bounded repair request.
Only `UNRESOLVED` after the sequence is terminal for that field. Numeric repair
requires a rejected numeric value, browser minimum, or grounded numeric preset;
it never turns an ungrounded answer into a generic zero.

## Deduplication and review records

One `AnswerResolver` instance belongs to one application session. It caches
provider results by field, issue kind, actual message, rejected value,
constraints, visible options, and candidate context. Repeating the same
validation state does not create another provider request or review record.

Only a final accepted `PROVIDER` or `DEFAULT` answer creates a `ReviewRecord`.
It includes job ID, company, title, original and normalized question, field
kind, visible options, final answer, source, confidence, reason, review flag,
validation message, and provider request count. Failed proposals and
intermediate repairs create no record. Milestone 2 creates records only;
actual CSV/Excel persistence is deferred to a later adapter milestone.
