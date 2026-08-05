# Form Orchestrator Milestone 3: extraction and writing

Milestone 3 adds offline domain and interaction boundaries for turning a live
form control into a Milestone 2 `FormField`, then writing one `AnswerResult`
back to that control and verifying the result. LinkedIn runtime integration is
deferred. This layer does not control navigation, application lifecycle, or
application accounting.

## Extractor interface

`FieldExtractor.extract(control, context)` reads a `FieldControl` snapshot and
returns an immutable `ExtractedField` containing:

- the `FormField` used by `AnswerResolver`;
- a serializable `FieldLocator`, never a live element;
- the original and normalized question;
- current browser validity and validation flags;
- bounded safe metadata about the control type.

Text inputs, textareas, numeric inputs, selects, radio groups, and checkboxes
are supported. Labels may be supplied by a label/legend adapter, `aria-label`,
or accessible text. Original Spanish punctuation and accents are retained;
normalization is used only for semantic comparison.

Hidden, disabled, and placeholder options are excluded from selectable
`FormField.visible_options`. Required whitespace-only text and a selected
placeholder are extracted as missing. Numeric values remain numeric strings,
and unchecked checkboxes remain explicit `False` values.

## Stable identity and locators

The field key is a SHA-256 digest over canonical JSON containing:

- normalized question;
- field kind;
- allowlisted stable DOM attributes;
- normalized visible-option signature;
- supplied application and job identifiers.

The digest is deterministic for an unchanged page and does not use Python's
process-dependent `hash()`. Locator attributes are allowlisted and never
include control values, candidate facts, page markup, or page HTML. Diagnostic
representations omit selector contents and redact answer text by length.

## Control boundary

`FieldControl` exposes only a safe immutable snapshot plus operations to clear
and enter text, select an option, or click a radio/checkbox choice.
`FieldControlProvider.requery(locator)` obtains the current control after a
page-owned DOM replacement. The protocols expose no driver, arbitrary script,
navigation, page lifecycle, or application-state methods.

Production browser adaptation is deliberately deferred. Milestone 3 tests use
fake controls exclusively.

## Writer interface and verification

`FieldWriter.write(WriteRequest, FieldControlProvider)` accepts only an
`ExtractedField` and `AnswerResult`. It does not resolve questions or call an
AI provider.

- A genuinely preserved answer that still matches and validates returns
  `SKIPPED_PRESERVED` without mutation.
- Text and textarea values are constraint-checked, cleared, entered, and read
  back without replacing their semantic content.
- Numbers reject booleans and free text, enforce min/max/step, and are compared
  numerically after writing.
- Select and radio answers must map semantically to a currently visible,
  enabled, non-placeholder option. Matching never falls back to the first
  option.
- Radio choices already in the requested state are not clicked again.
- Checkboxes accept explicit booleans. An optional unchecked marketing choice
  therefore remains untouched when the resolver returns `False`; truth policy
  stays in `AnswerResolver`, not the writer.

Every mutation is followed by a fresh query and verification of the value,
selected/checked state, constraints, and browser validity. If the first
verification fails, the writer re-queries and retries exactly once. It then
returns a structured `FAILED` result rather than looping or taking any
application-level action.

## Validation handoff

`ValidationState` exposes browser validity, the actual validation message,
`aria-invalid`, missing required values, type mismatch, range underflow and
overflow, step mismatch, text length failures, and required-option failures.
`FieldExtractor.validation_issues()` converts those flags into immutable
`ValidationIssue` values for the future orchestrator.

The future integration flow is:

```text
extract field
-> resolve answer
-> write and verify
-> navigation attempt
-> re-extract only invalid fields
-> create ValidationIssue
-> AnswerResolver.repair()
-> write repaired result
-> verify again
```

An ordinary initial validation failure remains repairable and does not imply
discarding an application. This milestone does not implement that navigation
loop, runtime review CSV persistence, or LinkedIn runtime integration.
