# Auto_job_applier_linkedIn Version History

## Audit scope and timestamp

- Repository: `<local-repository>/Auto_job_applier_linkedIn`. The private parent path is deliberately redacted.
- Audit timestamp: 2026-07-31 00:13:44 CEST (Europe/Madrid) for the current test run; Git and remote-ref inspection was performed in the same audit session.
- Scope: local branches, remote-tracking refs, live remote refs, tags, stashes, stash parent objects, archive tags, reflogs, object connectivity, version-line diffs, and the current offline test suite.
- Method: all current facts were re-read from Git. No branch was switched, no stash was applied, and no historical version was materialized.
- Audit modification history:
  - During the wider Git audit session, two local annotated preservation tags were deliberately created: `archive/v3-overengineered-backup-2026-07-25` and `archive/messy-login-debugging-2026-06-10`.
  - Both archive tags remain **LOCAL-ONLY / DO NOT PUSH**.
  - During the later Codex documentation and retest phase, only `docs/VERSION_HISTORY.md` was created or edited. No existing branch, stash, source file, test file, configuration file, or profile file was modified in that phase, and the pre-existing `config/settings.py` working-tree change was preserved.
- Evidence labels:
  - **Git-confirmed** means the claim follows from a current Git object, ref, ancestry query, diff, or live `git ls-remote` result.
  - **historically reported** means repository metadata makes the claim, but this audit did not reproduce it.
  - **external historical evidence** means evidence supplied by the user that is not stored in Git and was not reproduced by this audit.
  - **currently retested** means this audit ran the listed test command against the current working tree.
  - **unconfirmed** means neither current Git evidence nor a reliable repository artifact proves the claim.
- Privacy: remote ownership, private parent paths, and matched sensitive values are not reproduced. The sensitivity audit reports only category, repository-relative file, line, and baseline presence.

## Current repository state

| Item | Git-confirmed state |
| --- | --- |
| Current branch | `feature/gemini-minimal-fallback` |
| HEAD | `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3` |
| HEAD subject/date | `Add stable Gemini fallback and Easy Apply recovery`, 2026-07-30 23:20:43 +02:00 |
| Upstream | `origin/feature/gemini-minimal-fallback` |
| Upstream divergence | ahead 0, behind 0 |
| Staging area at audit start | empty |
| Working tree at audit start | exactly one tracked modification: `config/settings.py`, one insertion and one deletion |
| Working-tree configuration delta | line 89 changes `pause_before_submit` from committed `False` to working-tree-only `True` |
| Current stable tag | annotated `stable-gemini-fallback-v1`, tag object `8126d2e9cbde3a1e3a848b6475ad4e834352e1fb`, peeled target `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3` |
| Wider audit modifications | two local annotated archive tags were deliberately created; both remain **LOCAL-ONLY / DO NOT PUSH** |
| Later Codex documentation/retest phase | only `docs/VERSION_HISTORY.md` was created or edited; existing branches, stashes, source, tests, configuration, and profile files were not modified |

### Remotes

- `origin`: configured fork on `github.com`; owner and full URL are redacted. Live remote verification succeeded.
- `upstream`: `github.com/GodsScion/Auto_job_applier_linkedIn.git`. Live remote verification succeeded.
- Live `origin` branch tips relevant to this audit:
  - `feature/gemini-minimal-fallback` -> `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3`
  - `main` -> `455783e510827e58ba1722c6adcbe5d50062baeb`
- Live `upstream` tips relevant to this audit:
  - `main` -> `8d74e8ccb85b356fd7be15a70fe47ce85559261c`
  - `community-version` -> `b625dc810e282a49b3f6bba0493c5d73003eff37`
  - `dev` -> `ae160bc1ae6efb4634781f090e1a006f112c2a00`
  - `development` -> `f102408b4c7ac232e5e9d377af9785cf31565a62`
- The live upstream `main` object is not present in the local object database because this audit did not fetch. Its ancestry relative to local refs is therefore **unconfirmed**.

### Committed snapshot, working-tree setting, and browser evidence

- **Git-confirmed:** commit `d56660b` and its stable tag contain `pause_before_submit = False` through the committed `config/settings.py` inherited from `d56b9a0`.
- **Git-confirmed:** the current working tree changes that setting to `True`. This is **working tree only**, not committed, not tagged, and not protected by the remote stable branch.
- The annotation on `stable-gemini-fallback-v1` historically reports a browser-verified stable snapshot with multilingual Gemini fallback, deterministic facts, the review queue, submission recovery, and modal cleanup. It also records a possible delayed pagination-overlay limitation.
- Git alone cannot establish which dirty setting was active during a historical browser run. Separate **external historical evidence** from the 2026-07-30 validation session shows that the submit-confirmation pause was active, indicating that run used `pause_before_submit = True`.
- The real-browser validation therefore applies to the stable application code together with an uncommitted local setting. No browser run was repeated during the current audit.

### Current limitations

- No Selenium, LinkedIn, browser automation, live Gemini, or other provider call was run.
- Historical commits and stashes were not currently retested.
- The current offline suite tests the committed `d56660b` application code with the one pre-existing working-tree settings change present.
- `git fsck --full` found no dangling commits, but it found 548 dangling blobs and 36 dangling trees. Their contents were not printed. These loose recovery remnants are not durable refs and may be pruned.

## Branch inventory

### Local branches

| Branch | Tip | Tracking / remote | Ancestry and status | Safe recovery command after preserving changes |
| --- | --- | --- | --- | --- |
| `feature/gemini-minimal-fallback` | `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3` | tracks live `origin/feature/gemini-minimal-fallback`; 0 ahead, 0 behind | Current branch; one commit after `d56b9a0`; **committed**, **pushed**, **Git-confirmed** | `git switch feature/gemini-minimal-fallback` |
| `feature/gemini-ai-v2` | `2014b0f48bb3324ab4eb2fe18c111e751c6dd514` | no upstream; no matching live origin branch | Four commits after `d56b9a0`; parallel to minimal fallback; **local branch only**, historical | `git switch feature/gemini-ai-v2` |
| `main` | `d56b9a095d976de691f7d2ab1baac52f0159ddb8` | tracks `origin/main` | Relative to live/cached origin tip: ahead 5, behind 64; merge base `6836a95eb343c9cf7b5749c55bc7f9c074deb580`; **diverged local line** | `git switch main` |
| `log` | `393f36095e030fccd671f8a81c267870fba622ef` | none | Ancestor of local `main`; two commits behind local `main`; historical login/pause point; **local branch only** | `git switch log` |
| `my-backup-version` | `34f7488df63b4515859554986d71f4c08319546a` | none | Ancestor of local `main`; four commits behind local `main`; historical baseline; **local branch only** | `git switch my-backup-version` |

The merge base of `feature/gemini-ai-v2` and `feature/gemini-minimal-fallback` is exactly `d56b9a095d976de691f7d2ab1baac52f0159ddb8`. Their left/right count is 4/1. Neither branch is an ancestor of the other. Git therefore does **not** show that `feature/gemini-ai-v2` was merged into `feature/gemini-minimal-fallback`.

### Remote and remote-tracking branches

| Ref | Tip | State |
| --- | --- | --- |
| live `origin/feature/gemini-minimal-fallback` | `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3` | matches current branch |
| live/cached `origin/main` | `455783e510827e58ba1722c6adcbe5d50062baeb` | diverged from local `main`; cached and live tips match |
| cached `origin/community-version` | `b625dc810e282a49b3f6bba0493c5d73003eff37` | remote-only development line in this clone |
| cached `origin/dev` | `ae160bc1ae6efb4634781f090e1a006f112c2a00` | remote-only development line in this clone |
| cached `origin/development` | `f102408b4c7ac232e5e9d377af9785cf31565a62` | remote-only development line in this clone |
| live `upstream/main` | `8d74e8ccb85b356fd7be15a70fe47ce85559261c` | live server ref only; not fetched locally |

The reflog mentions deleted or transient branch names `log_in` and `TestJobApply`, but those entries point to already preserved commits, principally `34f7488`; they do not expose a unique reflog-only commit. `git rev-list --reflog --not --all` returned no commit.

## Tag inventory

| Tag | Type | Tag object | Peeled target | Local/remote status | Meaning |
| --- | --- | --- | --- | --- | --- |
| `stable-gemini-fallback-v1` | annotated | `8126d2e9cbde3a1e3a848b6475ad4e834352e1fb` | `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3` | local and live on `origin`; absent on `upstream` | Current stable tag; browser status historically reported in annotation |
| `login-fixed-v1` | lightweight | `937e65215529b8c13931fb7bc64c489ef2262a49` | same commit | local tag only | Dynamic login selector recovery point |
| `stable-login-pause-v1` | lightweight | `393f36095e030fccd671f8a81c267870fba622ef` | same commit | local tag only | Login plus pause-after-filter recovery point |
| `stable-skip-dismissed-v1` | lightweight | `af37278c72b7dce0189b6822865dc4a70775c83e` | same commit | local tag only | Dismissed-job skip recovery point |
| `archive/v3-overengineered-backup-2026-07-25` | annotated | `e1948882088d22adcef159834f5fe8dfad63a90e` | `df483db8d950c19b1185c0d1f185a62959bb483c` | **LOCAL-ONLY / DO NOT PUSH** | Durable ref to the v3 stash commit and all three parents |
| `archive/messy-login-debugging-2026-06-10` | annotated | `76822bcf857b22796a56243f030109591c134113` | `3a75af067fe4bbf8de85f8996698be124bbd52ce` | **LOCAL-ONLY / DO NOT PUSH** | Durable ref to the messy-login stash commit and both parents |

Both archive tags were created on 2026-07-31 00:04:19 +02:00. That is the tag creation time, not the stash creation time. Live `git ls-remote --tags` found only `stable-gemini-fallback-v1` on `origin` and no tags on `upstream`; neither archive tag is pushed.

`git tag --contains <commit>` reports tags whose reachable history contains a commit. It does not mean every listed tag points exactly at that older commit or was created to describe it. Exact targets above come from tag type and peeled-target inspection.

## Stash and archive inventory

### `stash@{0}` — v3-overengineered-backup

- **Identity:** `stash@{0}` is Git-confirmed as `v3-overengineered-backup`.
- **Stash commit:** `df483db8d950c19b1185c0d1f185a62959bb483c`
- **Date/origin:** 2026-07-25 00:24:35 +02:00, created on `feature/gemini-ai-v2`.
- **Base parent (`^1`):** `2014b0f48bb3324ab4eb2fe18c111e751c6dd514`
- **Index parent (`^2`):** `de96eddd6bb5fa7a3f92e46a23249fda82fcff59`, parent `2014b0f...`; its tree exactly equals the base tree, so there were no staged changes in the stash.
- **Untracked parent (`^3`):** `27677301cd2aa13b7394ffae104cd58c8fd5c55a`, a parentless commit containing the untracked tree.
- **Tracked worktree delta against base:** 11 files, 1,628 insertions, 259 deletions:
  - `config/candidate_profile.example.json`
  - `config/questions.py`
  - `config/search.py`
  - `config/settings.py`
  - `modules/ai/candidate_profile.py`
  - `modules/ai/deterministic_resolver.py`
  - `modules/ai/profile_fact_adapter.py`
  - `modules/ai/question_classification.py`
  - `runAiBot2.py`
  - `tests/test_candidate_profile.py`
  - `tests/test_profile_fact_adapter.py`
- **Untracked content:** 20 files, 9,213 insertions. It contains Gemini fallback and grounded-evidence modules, the `modules/ai/v3/` answer engine/candidate memory/evidence/relevance/runtime stack, and five related test modules.
- **Functional scope:** actual filenames and definitions show a broad v3 structured answer architecture, evidence retrieval, candidate memory, model contract, Gemini adapter, runtime adapter, job relevance, and integration tests. This is **stash only**, not a commit on the minimal-fallback line.
- **Against current stable `d56660b`:** the tracked stash tree differs in 22 files with 6,291 insertions and 9,951 deletions; its separate untracked parent adds the 20 v3/test files. This is not a patch-equivalent copy of the current implementation.
- **Test status:** test files exist, but this audit did not execute the stash. **Not currently retested**; no reliable count is recorded in repository metadata.
- **Archive:** annotated `archive/v3-overengineered-backup-2026-07-25` peels to the stash commit. The tag makes the base, index, and untracked parent reachable from a permanent local tag.
- **Remote:** no matching live origin or upstream tag/branch. **Local-only**.
- **Sensitivity:** **LOCAL-ONLY / DO NOT PUSH**. See the sanitized findings table below.
- **Inspect without applying:** `git show --stat df483db8d950c19b1185c0d1f185a62959bb483c` and `git diff df483db8^1 df483db8`.
- **Durable recovery:** prefer the archive tag/object ID, not stash ordinal: `git show --stat archive/v3-overengineered-backup-2026-07-25`. Recover only in an isolated, clean recovery worktree after reviewing the sensitivity warning.

### `stash@{1}` — messy login debugging

- **Stash commit:** `3a75af067fe4bbf8de85f8996698be124bbd52ce`
- **Date/origin:** 2026-06-10 21:39:51 +02:00, created on `main`.
- **Base parent (`^1`):** `34f7488df63b4515859554986d71f4c08319546a`
- **Index parent (`^2`):** `ebbb5d96aba6ad31acf23c8c2b35169340e141ec`, parent `34f7488...`; its tree exactly equals the base tree, so there were no staged changes.
- **Untracked parent:** none.
- **Tracked worktree delta against base:** 4 files, 154 insertions, 51 deletions: `config/questions.py`, `config/settings.py`, `modules/open_chrome.py`, and `runAiBot2.py`.
- **Functional scope:** actual diffs show login/browser-opening diagnostics and configuration/runtime experimentation. It predates the later committed login line.
- **Against current stable `d56660b`:** 12 files differ, with 237 insertions and 10,145 deletions, largely because the later minimal Gemini implementation and tests do not exist in this older stash tree.
- **Test status:** **not currently retested**; no reliable repository test record was found.
- **Archive:** annotated `archive/messy-login-debugging-2026-06-10` peels to this stash. The tag makes both stash parents reachable from a permanent local tag.
- **Remote:** no matching live origin or upstream tag/branch. **Local-only**.
- **Sensitivity:** **LOCAL-ONLY / DO NOT PUSH**. See the sanitized findings table below.
- **Inspect without applying:** `git show --stat 3a75af067fe4bbf8de85f8996698be124bbd52ce` and `git diff 3a75af0^1 3a75af0`.
- **Durable recovery:** prefer `archive/messy-login-debugging-2026-06-10` or the exact object ID, in an isolated clean recovery location.

### Sanitized archive sensitivity findings

No matched value is reproduced. `Earlier baseline = yes` means the exact matched literal was already present in the stash's committed base; it does not mean the value is safe to publish.

| Archive | Category | File and line | Earlier baseline |
| --- | --- | --- | --- |
| v3 | private local path | `config/questions.py:22` | yes |
| v3 | identity/contact literal | `config/questions.py:35` | yes |
| v3 | email address | `config/questions.py:97` | yes |
| v3 | email address | `runAiBot2.py:144` | yes |
| v3 | email address | `runAiBot2.py:642` | yes |
| v3 | credential-like literal | `tests/test_gemini_question_fallback.py:170` | no |
| v3 | email address | `tests/test_gemini_question_fallback.py:890` | no |
| v3 | identity/contact literal | `tests/test_gemini_question_fallback.py:890` | no |
| v3 | identity/contact literal | `tests/test_gemini_question_fallback.py:891` | no |
| v3 | email address | `tests/test_grounded_evidence.py:488` | no |
| v3 | email address | `tests/test_grounded_evidence.py:499` | no |
| v3 | email address | `tests/test_real_linkedin_regressions.py:286` | no |
| v3 | email address | `tests/test_real_linkedin_regressions.py:305` | no |
| v3 | email address | `tests/test_v3_runtime_integration.py:413` | no |
| v3 | email address | `tests/test_v3_runtime_integration.py:430` | no |
| v3 | email address | `tests/test_v3_runtime_integration.py:441` | no |
| messy login | private local path | `config/questions.py:22` | yes |
| messy login | identity/contact literal | `config/questions.py:35` | yes |
| messy login | email address | `config/questions.py:102` | yes |
| messy login | email address | `runAiBot2.py:93` | yes |
| messy login | email address | `runAiBot2.py:473` | yes |
| messy login | email address | `runAiBot2.py:718` | yes |
| messy login | email address | `runAiBot2.py:752` | yes |

This is a conservative literal-pattern scan, not a guarantee that the archives contain no other sensitive context. Neither archive should be pushed without a dedicated content review and a deliberate sanitized reconstruction.

## Important version ledger

### 1. Local refactor baseline

- **Version name:** local refactor baseline / `my-backup-version`
- **Date:** 2026-02-02 01:36:14 +01:00
- **Commit hash / tag / branch / stash:** `34f7488df63b4515859554986d71f4c08319546a`; branch `my-backup-version`
- **Parents:** `6836a95eb343c9cf7b5749c55bc7f9c074deb580`
- **Main functionality:** **Git-confirmed** refactor that removed tracked personal/secrets modules, expanded ignore/config handling, renamed the primary runtime to `runAiBot2.py`, and added `job_logger.py`.
- **Important changed files:** `.gitignore`, deleted `config/personals.py`, `config/secrets.py`, and `runAiBot.py`; modified `config/questions.py`, `config/search.py`, `config/settings.py`, `modules/ai/openaiConnections.py`, `modules/ai/prompts.py`, `modules/clickers_and_finders.py`, and `modules/validator.py`; added `error.png`, `job_logger.py`, and `runAiBot2.py`.
- **Test status:** **not currently retested**; no reliable version-specific test result found.
- **Commit status:** **committed**.
- **Push / remote status:** branch name is **local only** and there is no exact matching live branch/tag, but the commit is an ancestor of the pushed minimal-fallback branch.
- **Current or historical:** historical baseline; ancestor of both feature lines.
- **Known limitations:** diverges from modern upstream and predates later login and Gemini work.
- **Rollback or recovery command:** after preserving current changes, `git switch --detach 34f7488df63b4515859554986d71f4c08319546a` or `git switch -c recovery/refactor-baseline 34f7488df63b4515859554986d71f4c08319546a`.
- **Evidence source:** commit metadata, parent, diff-tree, stat, branch containment, live remote-ref audit.

### 2. Dynamic login selectors

- **Version name:** `login-fixed-v1`
- **Date:** 2026-06-10 21:55:42 +02:00
- **Commit hash / tag / branch / stash:** `937e65215529b8c13931fb7bc64c489ef2262a49`; lightweight tag `login-fixed-v1`
- **Parents:** `34f7488df63b4515859554986d71f4c08319546a`
- **Main functionality:** **Git-confirmed** stricter login-state detection and dynamic username/password input selectors in `login_LN`.
- **Important changed files:** `runAiBot2.py` only; 122 insertions, 21 deletions.
- **Test status:** **not currently retested**; no reliable version-specific result found.
- **Commit status:** **committed**.
- **Push / remote status:** tag is **local only** and no remote ref points exactly at the commit; the commit is nevertheless an ancestor of the pushed minimal-fallback branch.
- **Current or historical:** historical; ancestor of current stable.
- **Known limitations:** later pause and dismissed-card fixes are absent.
- **Rollback or recovery command:** `git switch --detach login-fixed-v1` or create `recovery/login-fixed-v1` from the tag.
- **Evidence source:** commit diff, function definitions, tag target, ancestry, live tag audit.

### 3. Login plus pause-after-search

- **Version name:** `stable-login-pause-v1`
- **Date:** 2026-06-10 22:11:59 +02:00
- **Commit hash / tag / branch / stash:** `393f36095e030fccd671f8a81c267870fba622ef`; lightweight tag and branch `log`
- **Parents:** `937e65215529b8c13931fb7bc64c489ef2262a49`
- **Main functionality:** **Git-confirmed** preservation of the login changes plus localized filter application and a pause-after-filter confirmation path.
- **Important changed files:** `config/questions.py`, `runAiBot2.py`; 46 insertions, 4 deletions.
- **Test status:** **not currently retested**; no reliable version-specific result found.
- **Commit status:** **committed**.
- **Push / remote status:** branch and tag names are **local only**; the commit is an ancestor of the pushed minimal-fallback branch.
- **Current or historical:** historical; ancestor of current stable.
- **Known limitations:** the later dismissed-job skip and Gemini lines are absent.
- **Rollback or recovery command:** `git switch --detach stable-login-pause-v1` or create `recovery/login-pause` from it.
- **Evidence source:** commit diff, tag/branch targets, ancestry, live tag audit.

### 4. Skip dismissed job cards

- **Version name:** `stable-skip-dismissed-v1`
- **Date:** 2026-06-11 13:22:32 +02:00
- **Commit hash / tag / branch / stash:** `af37278c72b7dce0189b6822865dc4a70775c83e`; lightweight tag `stable-skip-dismissed-v1`
- **Parents:** `393f36095e030fccd671f8a81c267870fba622ef`
- **Main functionality:** **Git-confirmed** detection and skipping of manually dismissed/hidden LinkedIn result cards before opening job details.
- **Important changed files:** `runAiBot2.py` only; 85 insertions, 20 deletions.
- **Test status:** **not currently retested**; no reliable version-specific result found.
- **Commit status:** **committed**.
- **Push / remote status:** tag is **local only**; the commit is an ancestor of the pushed minimal-fallback branch.
- **Current or historical:** historical; ancestor of current stable and both Gemini feature lines.
- **Known limitations:** predates Gemini diagnostics and both answer-engine implementations.
- **Rollback or recovery command:** `git switch --detach stable-skip-dismissed-v1` or create `recovery/skip-dismissed` from it.
- **Evidence source:** commit diff, tag target, ancestry, live tag audit.

### 5. Shared Gemini diagnostic baseline

- **Version name:** local `main` at `d56b9a0`
- **Date:** 2026-07-20 21:59:33 +02:00
- **Commit hash / tag / branch / stash:** `d56b9a095d976de691f7d2ab1baac52f0159ddb8`; local branch `main`
- **Parents:** `af37278c72b7dce0189b6822865dc4a70775c83e`
- **Main functionality:** **Git-confirmed** addition of two Gemini diagnostic scripts and ignore rules for environment files. This is the exact shared merge base of the v2 and minimal-fallback feature branches.
- **Important changed files:** `.gitignore`, `tools/list_gemini_models.py`, `tools/test_gemini.py`; 80 insertions.
- **Test status:** **not currently retested as an isolated version**. The diagnostic scripts were not run because this audit forbids live API calls.
- **Commit status:** **committed**.
- **Push / remote status:** no live ref points exactly at local `main`; its tracking branch has diverged (ahead 5, behind 64). The commit is the parent of the pushed minimal-fallback tip and is therefore reachable from that remote branch/tag.
- **Current or historical:** historical shared feature baseline.
- **Known limitations:** diagnostic tooling is not the runtime fallback; no answer-engine integration at this commit.
- **Rollback or recovery command:** `git switch --detach d56b9a095d976de691f7d2ab1baac52f0159ddb8` or create `recovery/gemini-baseline`.
- **Evidence source:** commit diff, merge-base queries, left/right counts, live remote audit.

### 6. v2 workflow-preservation commit

- **Version name:** v2 workflow preservation
- **Date:** 2026-07-21 00:36:44 +02:00
- **Commit hash / tag / branch / stash:** `f6b7888caa96dc35db15c96f9b129f93069a3378`; on `feature/gemini-ai-v2`
- **Parents:** `d56b9a095d976de691f7d2ab1baac52f0159ddb8`
- **Main functionality:** **Git-confirmed** narrow preservation changes to application question handling: additional Spanish city and salary keyword matching, plus configured question-value changes whose sensitive values are not reproduced.
- **Important changed files:** `config/questions.py`, `runAiBot2.py`; 5 insertions, 5 deletions.
- **Test status:** **not currently retested**; no reliable commit-specific result found.
- **Commit status:** **committed**.
- **Push / remote status:** reachable only from the **local branch** and local v3 archive tag.
- **Current or historical:** historical v2 line.
- **Known limitations:** no structured profile or decision engine yet.
- **Rollback or recovery command:** create a recovery branch from `f6b7888caa96dc35db15c96f9b129f93069a3378` after preserving changes.
- **Evidence source:** commit diff with configured values redacted, ancestry, ref containment.

### 7. Structured candidate profile schema

- **Version name:** v2 candidate profile schema
- **Date:** 2026-07-21 01:37:39 +02:00
- **Commit hash / tag / branch / stash:** `1d6ba455c5642fbbf720f7c772b8ff7f44ad3083`; on `feature/gemini-ai-v2`
- **Parents:** `f6b7888caa96dc35db15c96f9b129f93069a3378`
- **Main functionality:** **Git-confirmed** typed candidate-profile loading/validation and a committed example schema, with tests.
- **Important changed files:** `.gitignore`, `config/candidate_profile.example.json`, `modules/ai/candidate_profile.py`, `tests/test_candidate_profile.py`; 453 insertions, 1 deletion.
- **Test status:** test files exist, but this version is **not currently retested**.
- **Commit status:** **committed**.
- **Push / remote status:** **local branch only**, also reachable through the local v3 archive tag.
- **Current or historical:** historical v2 line.
- **Known limitations:** presence of tests does not establish that they passed; no decision engine yet.
- **Rollback or recovery command:** create `recovery/v2-profile-schema` from the full hash.
- **Evidence source:** commit diff/stat, definitions, ancestry, ref containment.

### 8. Structured application answer decision engine

- **Version name:** v2 answer decision engine
- **Date:** 2026-07-21 13:40:00 +02:00
- **Commit hash / tag / branch / stash:** `1142948c33860fa8b5a1e821d63d1e6afc86c705`; on `feature/gemini-ai-v2`
- **Parents:** `1d6ba455c5642fbbf720f7c772b8ff7f44ad3083`
- **Main functionality:** **Git-confirmed** answer policy, deterministic resolver, option matching, question classification/models, answer-decision validation, and a large unit-test module.
- **Important changed files:** `modules/ai/answer_policy.py`, `deterministic_resolver.py`, `option_matching.py`, `question_answering.py`, `question_classification.py`, `question_models.py`, and `tests/test_question_answering.py`; 3,017 insertions.
- **Test status:** **not currently retested**; test existence is not treated as a pass result.
- **Commit status:** **committed**.
- **Push / remote status:** **local branch only**, also reachable through the local v3 archive tag.
- **Current or historical:** historical v2 line.
- **Known limitations:** the profile fact adapter is added only by the next commit.
- **Rollback or recovery command:** create `recovery/v2-answer-engine` from `1142948c33860fa8b5a1e821d63d1e6afc86c705`.
- **Evidence source:** commit diff/stat, module definitions, ancestry, ref containment.

### 9. Safe candidate profile fact adapter

- **Version name:** v2 profile fact adapter
- **Date:** 2026-07-21 14:28:03 +02:00
- **Commit hash / tag / branch / stash:** `2014b0f48bb3324ab4eb2fe18c111e751c6dd514`; tip of `feature/gemini-ai-v2`, base of `stash@{0}`
- **Parents:** `1142948c33860fa8b5a1e821d63d1e6afc86c705`
- **Main functionality:** **Git-confirmed** conversion of validated profile records into deterministic fixed, experience, language, salary, availability, and legal facts, with resolver/classifier integration and tests.
- **Important changed files:** `modules/ai/deterministic_resolver.py`, `modules/ai/profile_fact_adapter.py`, `modules/ai/question_classification.py`, `tests/test_profile_fact_adapter.py`; 1,239 insertions, 14 deletions.
- **Test status:** **not currently retested**; no reliable version-specific pass record found.
- **Commit status:** **committed**.
- **Push / remote status:** tip of a **local branch only**; no live origin branch. Also permanently reachable from the local v3 archive tag.
- **Current or historical:** historical parallel implementation.
- **Known limitations:** not merged into the minimal-fallback branch; current stable uses different modules and tests.
- **Rollback or recovery command:** `git switch --detach 2014b0f48bb3324ab4eb2fe18c111e751c6dd514` or create `recovery/gemini-ai-v2`.
- **Evidence source:** commit diff/stat, definitions, merge-base/ancestry queries, live remote audit.

### 10. Current minimal Gemini fallback stable commit

- **Version name:** `stable-gemini-fallback-v1`
- **Date:** commit 2026-07-30 23:20:43 +02:00; annotated tag 2026-07-30 23:20:51 +02:00
- **Commit hash / tag / branch / stash:** `d56660bf2dc8b3b60cc78735e1c3d8ce71ee5ed3`; current branch and annotated stable tag
- **Parents:** `d56b9a095d976de691f7d2ab1baac52f0159ddb8`
- **Main functionality:** **Git-confirmed** minimal Gemini unknown-question fallback, bounded local profile resolution, deterministic multilingual/high-risk answers, answer review queue, validation/repair, Easy Apply recovery, success-modal polling/cleanup, and focused integration tests.
- **Important changed files:** `modules/ai/answer_review_queue.py`, `modules/ai/gemini_unknown_question.py`, `runAiBot2.py`, `tests/test_answer_review_queue.py`, `tests/test_gemini_unknown_question.py`, `tests/test_minimal_fallback_integration.py`; 9,850 insertions, 127 deletions.
- **Test status:** **currently retested** on 2026-07-31: 191 passed, 0 failed, 0 errors, 0 skipped. The tag annotation's browser verification is **historically reported** and is supported by the separately labeled external historical browser evidence below; neither was rerun here.
- **Commit status:** **committed**.
- **Push / remote status:** branch and annotated tag are **pushed** to `origin`; live refs match local objects.
- **Current or historical:** current stable committed application code. The `pause_before_submit=True` setting remains **working tree only**.
- **Known limitations:** no browser/API test in this audit. External historical evidence confirms that the 2026-07-30 browser validation used the submit-confirmation pause and eventually encountered the delayed pagination-overlay interception; `pause_before_submit=True` remains uncommitted and unprotected by the stable commit, tag, and remote branch.
- **Rollback or recovery command:** after preserving changes, `git switch --detach 'stable-gemini-fallback-v1^{}'` or create a recovery branch from `origin/feature/gemini-minimal-fallback` after verifying/fetching it.
- **Evidence source:** commit/tag objects, live origin refs, diff/stat, current offline tests, tag annotation.

### 11. Stash/archive recovery points

- **Version name:** v3-overengineered stash/archive
- **Date:** stash 2026-07-25; archive tag 2026-07-31
- **Commit hash / tag / branch / stash:** `df483db8d950c19b1185c0d1f185a62959bb483c`; `stash@{0}`; `archive/v3-overengineered-backup-2026-07-25`
- **Main functionality:** broad v3 structured/evidence-based runtime and tests, plus tracked v2-line edits.
- **Important changed files:** the 11 tracked and 20 untracked files listed in the stash inventory.
- **Test status:** **not currently retested**.
- **Commit status:** **stash only**, not a normal product commit.
- **Push / remote status:** **local tag only / do not push**.
- **Current or historical:** historical recovery point.
- **Known limitations:** sensitive-content findings, parallel architecture, likely conflicts with current stable.
- **Rollback or recovery command:** inspect by exact object/archive tag; apply only in an isolated recovery worktree.
- **Evidence source:** stash commit parents/trees, archive peeled target, diffs, sensitivity scan.

- **Version name:** messy-login stash/archive
- **Date:** stash 2026-06-10; archive tag 2026-07-31
- **Commit hash / tag / branch / stash:** `3a75af067fe4bbf8de85f8996698be124bbd52ce`; `stash@{1}`; `archive/messy-login-debugging-2026-06-10`
- **Main functionality:** login/browser-opening and configuration debugging edits.
- **Important changed files:** `config/questions.py`, `config/settings.py`, `modules/open_chrome.py`, `runAiBot2.py`.
- **Test status:** **not currently retested**.
- **Commit status:** **stash only**.
- **Push / remote status:** **local tag only / do not push**.
- **Current or historical:** historical recovery point.
- **Known limitations:** sensitive-content findings and very old runtime base.
- **Rollback or recovery command:** inspect by exact object/archive tag; apply only in an isolated recovery worktree.
- **Evidence source:** stash commit parents/trees, archive peeled target, diffs, sensitivity scan.

## Version-line comparison

### Local main line

The local line is:

`34f7488` -> `937e652` -> `393f360` -> `af37278` -> `d56b9a0`

From `34f7488` to `d56b9a0`, Git reports five changed files, 315 insertions, and 27 deletions: `.gitignore`, `config/questions.py`, `runAiBot2.py`, and two added Gemini diagnostic scripts. This line contains the local refactor, login, pause-after-search, dismissed-card skip, and Gemini diagnostics.

Local `main` is not the same line as live `origin/main`. They share `6836a95eb343c9cf7b5749c55bc7f9c074deb580`, after which local `main` has five unique commits and origin has 64 unique commits.

### `feature/gemini-ai-v2` line

This branch adds four commits after `d56b9a0`: workflow preservation, a typed candidate profile, a structured answer-decision engine, and a profile fact adapter. From `d56b9a0` to `2014b0f`, Git reports 15 files, 4,700 insertions, and 6 deletions. Its current tip is local-only.

### `feature/gemini-minimal-fallback` line

This branch adds one large commit after `d56b9a0`. From the shared base to `d56660b`, Git reports six files, 9,850 insertions, and 127 deletions. It implements its own small AI modules plus extensive direct runtime integration and tests. Its branch and stable tag are pushed to origin.

### Why the feature lines are parallel

Git proves a shared merge base `d56b9a0`, a 4/1 left/right divergence, and no ancestry in either direction. The file comparison also shows different architectures:

- v2 has `answer_policy`, `candidate_profile`, `deterministic_resolver`, `option_matching`, `profile_fact_adapter`, `question_answering`, `question_classification`, and `question_models`.
- minimal fallback instead has `answer_review_queue` and `gemini_unknown_question`, plus much larger direct changes in `runAiBot2.py` and different test modules.

Comparing `2014b0f` to `d56660b` reports 20 files: 9,856 insertions and 4,827 deletions. The apparent deletions are not a later removal from a merged line; they are the consequence of comparing parallel children of the same base.

### Required point comparisons

- `34f7488 -> d56b9a0`: 315 insertions, 27 deletions across five files; login/pause/dismissed-card fixes and Gemini diagnostics accumulate on the local line.
- `d56b9a0 -> 2014b0f`: 4,700 insertions, 6 deletions across 15 files; the structured v2 stack.
- `d56b9a0 -> d56660b`: 9,850 insertions, 127 deletions across six files; the minimal fallback/current stable stack.
- `2014b0f <-> d56660b`: parallel architectures, 4/1 commit divergence, same merge base, neither merged into the other.
- `stash@{0} -> base`: 11 tracked files with 1,628 insertions/259 deletions, plus 20 untracked files with 9,213 insertions.
- `stash@{1} -> base`: 4 tracked files with 154 insertions/51 deletions; no untracked parent.
- Each stash differs heavily from `d56660b`; neither is a drop-in current-stable replacement.

## Test status

### Historical test evidence

- The annotation of `stable-gemini-fallback-v1` says the snapshot was browser verified and lists its intended functional scope. This is **historically reported**. It gives no test count or command.
- No durable repository log or metadata was found that establishes pass counts for `34f7488`, the login tags, the v2 commits, either stash, or either archive.
- Old commit subjects containing words such as “tested” are not treated as current evidence for the versions in this ledger.

### External historical browser evidence supplied by the user

**Evidence source:** “External user-provided runtime log from 2026-07-30; not stored in Git and not currently retested.”

- A real browser run reported 17 Jobs Easy Applied, 2 failed jobs, and 1 irrelevant job skipped.
- Multiple successful applications logged `success_accounted=true` and `modal_remains_open=false`.
- The run continued successfully across multiple applications.
- It eventually stopped when a residual LinkedIn Artdeco modal overlay intercepted the pagination “View next page” button.
- The active submit-confirmation pause indicates that this validation session used `pause_before_submit=True` with the stable application code, even though the committed `d56660b` setting is `False`.
- This external historical evidence supports the stable tag's browser-verification description and confirms the documented delayed-pagination-overlay limitation.
- No browser run was repeated during the current audit.

### Current audit retest

- Date: 2026-07-31 00:13:44 CEST.
- Interpreter: `.venv/bin/python`, Python 3.11.12.
- Test framework: standard-library `unittest` available; `pytest` not installed.
- Command: `.venv/bin/python -m unittest discover -s tests -v`
- Result: **191 passed, 0 failed, 0 errors, 0 skipped** in 2.784 seconds.
- Test files: `tests/test_answer_review_queue.py`, `tests/test_gemini_unknown_question.py`, `tests/test_minimal_fallback_integration.py`.
- Limitations: offline/synthetic only; no Selenium, LinkedIn, browser, live Gemini, or network-dependent provider test. Historical refs were not checked out or currently retested.

### Unknown

All historical versions and both stash/archive trees remain **not currently retested** unless explicitly marked otherwise above. Test-file presence is not evidence of a passing run.

## Recovery procedures

### Preserve current changes first

Before any branch switch or recovery operation:

```bash
git status --short --untracked-files=all
git diff -- config/settings.py
git diff > <safe-external-location>/working-tree.patch
git stash push --include-untracked -m "pre-recovery-working-tree"
git stash list
```

`git stash --include-untracked` does not include ignored files. Any ignored local profile or other ignored data must be backed up separately to an access-controlled location without printing its contents.

Do not use `git reset --hard` as a routine recovery command. It destroys uncommitted tracked work; together with cleaning commands it can cause broader data loss.

### Inspect a historical commit without moving a branch

```bash
git switch --detach <full-commit-hash>
```

Return only after verifying the worktree is clean and preserving any new work.

### Create a recovery branch

```bash
git switch -c recovery/<descriptive-name> <full-commit-hash-or-peeled-tag>
```

Examples of durable local recovery targets are `34f7488...`, `login-fixed-v1`, `stable-login-pause-v1`, `stable-skip-dismissed-v1`, `2014b0f...`, and `stable-gemini-fallback-v1^{}`.

### Recover a local branch

After preserving changes, use its existing name:

```bash
git switch main
git switch feature/gemini-ai-v2
git switch feature/gemini-minimal-fallback
git switch log
git switch my-backup-version
```

Do not run these as a batch; choose exactly one target after reviewing `git status`.

### Inspect a stash without applying it

```bash
git show --stat df483db8d950c19b1185c0d1f185a62959bb483c
git diff df483db8^1 df483db8
git ls-tree -r --name-only df483db8^3

git show --stat 3a75af067fe4bbf8de85f8996698be124bbd52ce
git diff 3a75af0^1 3a75af0
```

Use exact object IDs because stash ordinals can change.

### Recover from an archive tag

First inspect the tag and parents:

```bash
git show --stat archive/v3-overengineered-backup-2026-07-25
git show --stat archive/messy-login-debugging-2026-06-10
```

For actual recovery, use a separate clean worktree so the current working tree is untouched:

```bash
git worktree add <safe-recovery-directory> 2014b0f48bb3324ab4eb2fe18c111e751c6dd514
git -C <safe-recovery-directory> stash apply df483db8d950c19b1185c0d1f185a62959bb483c
```

For the messy-login archive, use base `34f7488...` and stash object `3a75af0...`. Applying can conflict and may materialize sensitive literals; keep the recovery directory local and do not push it.

### Restore or recover the current stable remote branch

Verify the server first, preserve the working tree, then create a separate recovery branch rather than rewriting the current branch:

```bash
git ls-remote origin refs/heads/feature/gemini-minimal-fallback refs/tags/stable-gemini-fallback-v1
git fetch origin feature/gemini-minimal-fallback
git switch -c recovery/stable-gemini-fallback origin/feature/gemini-minimal-fallback
```

If operating on the existing branch instead, use only a fast-forward merge after preservation and verification:

```bash
git switch feature/gemini-minimal-fallback
git merge --ff-only origin/feature/gemini-minimal-fallback
```

## Known risks and preservation status

- Local `main` diverges from `origin/main` by 5 local-only and 64 origin-only commits. Neither side should overwrite the other without an explicit integration plan.
- The live upstream `main` tip was verified remotely but not fetched; local ancestry against it remains unconfirmed.
- The v2 branch, `log`, `my-backup-version`, five local-only tags: three historical lightweight tags and two annotated archive tags, and both stashes are not pushed.
- Both archive tags are **LOCAL-ONLY / DO NOT PUSH** because sanitized scanning found private-path, contact/email, and in one archive credential-like literal categories. The values were not printed or rewritten.
- **Git-confirmed:** the current `pause_before_submit=True` setting is working-tree-only and is not protected by commit `d56660b`, the stable tag, or the remote branch. **External historical evidence** indicates that the 2026-07-30 browser validation used this enabled pause with the stable application code.
- Stash order can change. Prefer exact object IDs and archive tags for preservation and recovery.
- Archive tags currently make every stash commit and stash parent, including the v3 untracked parent, reachable from permanent local refs.
- `git fsck` found no dangling commit, but 548 dangling blobs and 36 dangling trees are not protected recovery points and may be pruned.
- The stable tag's browser status is historical metadata. This audit confirms only the 191-test offline suite; live runtime behavior remains outside this audit.
- During the wider Git audit session, the two annotated local archive tags listed above were deliberately created and remain **LOCAL-ONLY / DO NOT PUSH**.
- During the later Codex documentation and retest phase, only `docs/VERSION_HISTORY.md` was created or edited. No existing branch, stash, source file, test file, configuration file, or profile file was modified; the pre-existing `config/settings.py` delta was preserved exactly.

## Evidence appendix

The following commands, or equivalent formatting-limited variants, were used. Outputs containing remote ownership or sensitive literals were sanitized before documentation.

```bash
pwd
git status --porcelain=v2 --branch
git status --short --untracked-files=all
git remote -v
git branch --all --verbose --verbose
git show-ref --heads --tags
git show-ref -d --heads --tags
git for-each-ref refs/heads refs/remotes refs/tags
git log --all --graph --decorate --oneline --date-order
git tag -n100
git stash list
git reflog --all --date=iso
git fsck --full
git fsck --full --no-reflogs
git rev-list --left-right --count <left>...<right>
git merge-base <left> <right>
git merge-base --is-ancestor <left> <right>
git rev-list --reflog --not --all
git ls-remote origin <relevant-refs>
git ls-remote upstream <relevant-refs>
git ls-remote --tags origin
git ls-remote --tags upstream
git show -s --format=<sanitized-metadata> <object>
git diff-tree --no-commit-id --name-status -r <commit>
git diff --stat <left> <right>
git diff --name-status <left> <right>
git diff --shortstat <left> <right>
git ls-tree -r --name-only <stash-untracked-parent>
git for-each-ref --contains <object> refs/heads refs/tags refs/remotes
git rev-parse <ref>^{tree}
git count-objects -v
test -x .venv/bin/python
.venv/bin/python --version
.venv/bin/python -m unittest discover -s tests -v
```

No API key, secret value, profile content, provider prompt, browser page source, or PII value is included in this ledger.
