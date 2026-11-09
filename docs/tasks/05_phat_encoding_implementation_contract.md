# Implementation Contract — Feature Encoding & Matrices (Phát)

> **Status:** Analysis only — no implementation decision is made by this document.  
> **Scope:** `preprocessing/encoding/` and its declared P5 outputs.  
> **Evidence basis:** SPEC-01…13, `AGENTS.md`, `preprocessing/CLAUDE.md`, P5 local specification, task brief, the approved decision supplied on 2026-11-07, and repository state inspected on 2026-11-07.

## Normative-reading convention

- **SPEC requirement** states what the cited document requires.
- **Current repository state** describes existing code/configuration; it is not automatically a requirement.
- **Engineering recommendation** is a non-normative implementation/testing suggestion.
- **Unresolved decision** marks a missing or conflicting rule that must be approved before implementation.

The hierarchy for current preprocessing policy is `AGENTS.md` and `preprocessing/CLAUDE.md`; in particular they prohibit LLM/model use and JD translation. This document does not silently reconcile conflicts with older SPEC prose.

## Approved decision register

| Decision | Status and exact effect | Boundaries retained |
|---|---|---|
| **Multi-hot width is exactly 230 skill columns** | **Approved by the responsible owner (2026-11-07).** The skill submatrix X has one row per job and exactly 230 binary skill columns. It must not shrink dynamically to 200 or fewer. Co-occurrence C consequently has shape 230×230 and the same ordered vocabulary. | This approval does **not** by itself choose the 230 skills, add taxonomy entries, waive the frequency ≥20 rule, define a fallback for insufficient eligible skills, alter P5 ownership, alter column prefix, or change any original SPEC. |

## 1. Input contract

### Canonical input

| Classification | Contract |
|---|---|
| **SPEC requirement** | P5 input is `data/preprocessing/04_normalization/all.parquet` (`docs/spec/preprocessing/spec/P5_encoding.md` §2). |
| **Current repository state** | `preprocessing/encoding/run.py` uses exactly that path as `IN_FILE`. It reads with `pandas.read_parquet`. No input Parquet is present in the inspected workspace, so its physical Arrow schema was not verified. |
| **Engineering recommendation** | Validate the Parquet schema before transformation and fail with an actionable missing-column/type report; do not infer a schema from missing values. |

### Required columns for the current P5 implementation

The following columns are directly indexed by `encode_dataset()` and therefore are required by the **current code**, unless noted optional. Types below are logical types, not an unverified Arrow schema.

| Column | Logical type / allowed null | Use |
|---|---|---|
| `job_id_global` | unique, non-null string | output row key |
| `seniority` | nullable label string | E1 ordinal |
| `job_family` | nullable label string, normally one of P4 families plus `Khác` | E2 |
| `source_platform` | non-null source string | E2 and optional source filtering |
| `raw_employment_type` | nullable string | E2 |
| `locations` | nullable/list-like list of objects with optional `tinh_key`, `remote`, `ngoai_vn` | E3 |
| `skills_std` | nullable/list-like list of canonical skill strings | E4 |
| `log_salary_min`, `log_salary_max`, `exp_min_years`, `exp_max_years`, `headcount` | nullable numeric | E5 |
| `is_negotiable`, `is_outlier_salary` | nullable boolean-like | E6 |
| `posted_date`, `deadline_date` | nullable parseable date/time or string | E7 |
| `it_rule_level`, `seniority_can_kiem`, `job_family_can_kiem` | optional in current code; nullable numeric/boolean-like | E8 flags |

P4 itself produces `locations`, `tinh_chinh`, `seniority`, `job_family`, `skills_std`, salary log fields and `is_outlier_salary` (`preprocessing/normalization/run.py`, `KEY_FIELDS` and processing logic). It canonicalizes `skills_std` from `skills_clean` through `canonicalize_skills()`. P4 does not establish a formal published Arrow schema in the reviewed documents.

### Missing and upstream assumptions

- **SPEC requirement:** P5 preserves row count; does not modify normalized values; continuous nulls remain `NaN` and receive a `__missing` indicator (P5 §4–5). Salary MNAR must not be mean/median/mode-imputed (SPEC-05 §4.2; `AGENTS.md`).
- **Current repository state:** unknown seniority becomes `-1`; null booleans become `0`; unparseable dates become null numeric outputs with indicators. `locations`/`skills_std` are only iterated when `hasattr(value, "__iter__")`; a string would be iterated character-by-character, so its type is a material precondition.
- **Unresolved decision:** no source specifies whether missing/invalid `job_id_global`, duplicate IDs, unknown `source_platform`, malformed list elements, or a zero-row input must fail versus be retained and reported.

## 2. Skill dictionary and multi-hot matrix

### Dictionary source and canonicalization

- **SPEC requirement:** the taxonomy is `preprocessing/dictionaries/skills.json`; aliases are normalized to canonical names, with short names such as C/R/Go requiring contextual matching (SPEC-06 §3.1–3.2; `preprocessing/CLAUDE.md`). P4 is responsible for this mapping, so P5 consumes `skills_std`, not raw JD skill matching.
- **Current repository state:** P4 calls `canonicalize_skills`; P5 lowercases/slugs canonical strings with `to_col_slug()` and resolves collisions by retaining the longer spelling in `skills_map`. P5 does not directly read `skills.json`.
- **Engineering recommendation:** make P5 reject or report canonical skill values not representable in the approved taxonomy rather than creating a second, divergent taxonomy. Preserve canonical label, slug, frequency, index, selection rule and dictionary version in its metadata.
- **Current repository state — verification:** `preprocessing/dictionaries/skills.json` contains **40** top-level canonical skill names. It is therefore not, in its current state, a 230-item vocabulary. The P4 input Parquet is not present in this workspace, so neither the number of observed canonical skills nor how many meet frequency ≥20 could be verified.
- **Unresolved decision:** no authoritative document defines a fixed, versioned 230-item ordered vocabulary, category quota, collision policy, taxonomy version field, or whether new canonical entries may be added to reach 230.

### Selection and column order

| Classification | Contract |
|---|---|
| **Approved decision** | exactly 230 binary skill columns in X; this supersedes any dynamic maximum below 230 for matrix width, but does not repeal the conflicting source requirements listed below. |
| **Task requirement** | exactly 230 IT skills, balanced across six taxonomy groups; columns use `skill_` examples (`docs/tasks/05_phat_encoding_and_matrices.md` §1, §3). |
| **SPEC-06 requirement** | select skills occurring at least 20 times, normally K in `[100, 200]` (SPEC-06 §5.1). |
| **Current P5 requirement/state** | P5 proposes/implements frequency ≥20, at most 200, dynamically chosen in `Counter.most_common()`; emitted columns use `skill__<slug>` (P5 §4; `run.py`). |
| **Unresolved decision** | The width conflict is now resolved **only** in favor of 230. Fixed vocabulary versus run-dependent top-K, six-group balancing, frequency ≥20 treatment, the fallback when fewer than 230 skills qualify, and `skill_` versus `skill__` prefix remain unresolved. Approval is required before changing either producer or mining consumer. |

**Engineering recommendation:** after approval, sort selected skills by a deterministic documented key (for example fixed dictionary index, then canonical name) and persist `index → canonical_name → column_name`. Frequency ties must have an explicit deterministic tie-breaker. This is a recommendation, not a declared requirement.

### Matrix semantics

For each retained skill `j`, `X[i,j] = 1` iff the deduplicated canonical `skills_std` list for job `i` contains that skill; otherwise 0. **Approved:** X has exactly 230 columns. Values must be `uint8`/binary. A selected vocabulary member absent from all observed jobs remains an all-zero column if the approved vocabulary is fixed; whether this is permitted is otherwise not specified. Skills outside the selected vocabulary increment `skills__other_count` in current P5. A job with no recognized skill has an all-zero selected-skill row; it must not be dropped.

The precise column names, ordered 230-item selection list, tie-breaker, treatment of below-threshold skills, handling of skills absent from input, and status/definition of `skills__other_count` remain **Unresolved Decisions**. The sentence above records current behavior where it exists; it does not authorize it as the 230-column solution.

## 3. Skill co-occurrence contract

- **SPEC requirement:** `C = XᵀX`; `C[j,k]` counts postings containing both skills; C is symmetric and `C[j,j]` equals the independent frequency (SPEC-06 §5.2).
- **Approved decision / task requirement:** co-occurrence is computed from the exact 230-column X, is 230×230, and its row/column ordering corresponds exactly to the persisted ordered skill vocabulary. The task names `data/preprocessing/05_encoding/skill_cooccurrence.parquet` and requires symmetry/diagonal validation (§1 and §3).
- **Current repository state:** no co-occurrence constant, computation, test, R2 export key, or output exists in `preprocessing/encoding/run.py` or `preprocessing/common/r2_export.py`.
- **Unresolved decision:** SPEC-06 names `matrix_skill_cooccurrence.parquet`; the task names `skill_cooccurrence.parquet`. Neither defines long/wide schema, dtypes, labels/index storage, compression, or whether zero-frequency vocabulary entries are retained. Do not select a filename or schema without approval.

**Engineering recommendation:** compute from the exact persisted X column order using an integer-safe sparse/dense multiplication; retain zero-frequency selected skills as all-zero rows/columns only if the vocabulary is fixed. Validate shape 230×230, label order, non-negative integer entries, symmetry, and `diag(C) == X.sum(axis=0)`.

## 4. TF-IDF contract

| Aspect | Evidence and status |
|---|---|
| Text input | **Task:** `job_description + job_requirements`. **Current repo:** normalized data supplies `description_clean` and `requirements_clean`; it has no fields literally named by the task. **Unresolved:** authoritative final source field names are not contracted. |
| Cleaning | **SPEC-05:** HTML/boilerplate removal and Unicode NFC occur upstream. **SPEC-07:** remove Vietnamese and English technical stopwords. **Current P5:** explicitly says P5 does not encode JD; TF-IDF/embedding belongs to analysis. |
| Vectorizer | **SPEC-06 §5.3:** `TfidfVectorizer`, word ngrams `(1,2)`, `min_df=5`, `max_df=.8`, `max_features=3000`. **Task:** 2,000–3,000 features. **SPEC-07 §3.1:** K=100 important ngrams and L2-normalized concatenated vector. This is unresolved. |
| Persistence | **Task/SPEC-10:** demand a stored TF-IDF matrix/vector space. **Current repo:** no TF-IDF artifact, vocabulary, job-id mapping, output path, or R2 export key. |

No document defines stopword asset path/version, analyzer/tokenizer for Vietnamese, `lowercase`, `strip_accents`, `dtype`, vocabulary JSON schema, sparse serialization format, or a row-order mapping. Those are **unresolved decisions**, not implied requirements.

**Engineering recommendation:** persist an explicit `job_id_global` row mapping and vocabulary/parameters metadata alongside any sparse matrix; never rely on DataFrame row position alone.

## 5. Gold and artifact contract

| Artifact | Classification / declared path | Current repository state | Consumer |
|---|---|---|---|
| Normalized input | `data/preprocessing/04_normalization/all.parquet` | P4 output; no local file inspected | P5 |
| Feature table | `data/preprocessing/05_encoding/features.parquet`, Parquet, one row/job, key + numeric fields (P5); its skill submatrix is **exactly 230 columns by approved decision** | implemented, but currently dynamic max 200; `pyarrow`, no explicit compression | FP-Growth; K-Means current example |
| Encoding dictionary | `data/preprocessing/05_encoding/encoding_dictionary.json` | implemented | human/reversibility; required for feature semantics |
| P5 report | `reports/preprocessing/05_encoding/_all.json` | emitted by `StepReport` | Monitoring |
| Golden dataset | `data/curated/curated_flat_golden_jobs.parquet` (SPEC-01/03/07/13; task) | P5 explicitly must not modify Golden; no P5 write exists | Mining spec and RF command |
| Co-occurrence | 230×230 from the approved X; task `.../skill_cooccurrence.parquet`; SPEC-06 `matrix_skill_cooccurrence.parquet` | absent | skill graph/community analysis, not a specified mining CLI input |
| TF-IDF matrix + vocabulary/mapping | task/SPEC-06/10 request it, path/schema omitted | absent | K-Means/HDBSCAN + PCA |

Only `features.parquet`, dictionary, and report are P5 artifacts supported by current code/R2 mapping. `r2_export.GOLD_KEYS` exports only the first two to `curated/preprocessing/`. No source designates whether co-occurrence/TF-IDF are official Gold artifacts or intermediate analysis artifacts.

## 6. Downstream compatibility

| Consumer | Required input evidence | Compatibility conditions |
|---|---|---|
| FP-Growth | SPEC-07 reference code selects columns `startswith("skill_")`, casts boolean. | It must receive exactly the approved 230 binary X columns and exclude IDs, `skills__other_count`, flags and numeric fields. Prefix must align: current `skill__` does satisfy `skill_` prefix, but `skills__other_count` also satisfies it and would incorrectly be selected. This is a current-repo compatibility defect/gap, not an approved change request. |
| K-Means/HDBSCAN + PCA | SPEC-07 requires skills + TF-IDF, K=100 in §3.1; SPEC-06/task say TF-IDF 3,000/2,000–3,000. | Stable job alignment between X and TF-IDF; deterministic vocabulary; documented feature concatenation, scaling/normalization and missing-value handling are required but not contracted. Current reference uses only `skill_` columns, not TF-IDF. |
| Random Forest/SHAP | SPEC-07 §4 requires skills + experience + seniority + location + job family; salary target is log midpoint. SPEC-13 invokes it with Golden dataset. | A join key and exact training table are undefined. Current P5 outputs `skill__`, `exp_` is not emitted (only `exp_min_years`), `sen_`, `loc_`, `jf_` prefixes in SPEC reference do not match current column names. Salary midpoint is not emitted in current features. This downstream contract is unresolved. |

## 7. Validation and testing

### Invariants

- Row conservation: `rows(features) == rows(input)`; P5 must not filter jobs.
- `job_id_global` preserves one-to-one row alignment; uniqueness handling remains undecided.
- All feature columns except ID are numeric; binary/one-hot/multi-hot values are in `{0,1}` and use compact integer types where declared.
- Missing continuous/date feature values remain missing and their indicator equals `isna`.
- Dictionary resolves every encoded categorical/skill column and records selected top-K/top-10 thresholds.
- For X/C when approved: C shape/order match X, symmetry, non-negative integral counts, and diagonal/frequency equality.
- For TF-IDF when approved: row count/mapping align with X, vocabulary cardinality matches matrix width, no NaN/Inf, parameters/vocabulary are persisted.

### Existing coverage and required levels

- **Current repository state:** `tests/unit/test_encoding_step.py` covers E1–E8, numeric output, dictionary reversibility and some missing/multi-hot cases. Its fixture uses a synthetic DataFrame; it does not test file output, matrices, TF-IDF, Parquet schema, compression, 230-column width/order or downstream consumers.
- **Engineering recommendation — unit:** exact 230-column width once an approved vocabulary exists; slug collisions; duplicate skills within a job; null/empty/non-list arrays; empty input; fewer than 230 eligible skills; exact frequency threshold; ties; unknown taxonomy values; selected-but-unobserved skills; jobs with no valid skill; date inversion; all-null numeric fields.
- **Engineering recommendation — integration:** run P4 fixture → P5 and assert report, input/output row conservation, dictionary consistency, and R2 planning includes every approved official P5 artifact.
- **Engineering recommendation — data validation:** inspect real input only when it exists; assert schema/invariants without network. Tests must remain offline under SPEC-12.

**Acceptance evidence already stated:** P5 requires all-numeric feature columns, equal row count, and reverse-decode of five jobs; the task adds exactly 230 skill columns, co-occurrence validation, parquet size/read benchmark, and Ruff. These acceptance targets conflict as recorded below and need resolution before a single acceptance gate is asserted.

## 8. Conflict and gap report

| Topic | Sources and conflicting text | Classification / required disposition |
|---|---|---|
| Skill count | **Approved decision:** exactly 230 matrix columns. Task §1/§3: exactly 230; SPEC-06 §5.1: normally 100–200; P5 §4: proposed max 200; current code max 200. | **Width is resolved by the approved decision.** The remaining conflict is implementation state/spec text still specifying ≤200 and must be updated only when separately authorized. |
| Taxonomy capacity | Task requires 230 across six groups. Current `skills.json` has 40 canonical keys; no P4 dataset is available locally to measure frequency eligibility. | **New verified gap.** No source authorizes taxonomy expansion, synthetic skills, duplicates, or threshold relaxation to obtain 230. |
| Fixed vocabulary / frequency | SPEC-06 and P5 use frequency ≥20/dynamic top-K; approved width requires 230 but defines no fallback when fewer qualify. | **Unresolved decision.** Retain the ≥20 requirement as effective SPEC text until an owner explicitly decides its interaction with the approved 230 width. |
| Six taxonomy groups | Task requires balanced coverage across six groups; `skills.json` is a flat 40-key object and no source defines quotas or each key’s group metadata. | **Unresolved decision / documentation gap.** |
| Skill prefix and selection | Task: `skill_`; P5/current code: `skill__`; SPEC-07 selector `skill_` also unintentionally captures `skills__other_count`. | **Unresolved decision plus current compatibility risk.** |
| TF-IDF ownership | Task and SPEC-06/10 request P5/Gold TF-IDF; P5 §4 and prompt §4 say no JD encoding in P5, do it in analysis. | **Unresolved decision.** |
| TF-IDF width | Task 2,000–3,000; SPEC-06 §5.3=3,000; SPEC-07 §3.1=100. | **Unresolved decision.** |
| Text language/LLM | SPEC-05 §2.5 and SPEC-06 §4.3 prescribe language detection/translation; `AGENTS.md`, `preprocessing/CLAUDE.md`, P5 supersession state zero-LLM/no translation. | **Current policy is deterministic/no LLM/no translation; older provisions are superseded for implementation.** |
| E6/E8 fields | P5 table asks `it_status` one-hot and probability fields `it_prob`, `seniority_prob`, `job_family_prob`; current code/tests instead omit `it_status`, emit deterministic rule flags. P5 header says JEV/LLM material is obsolete. | **Current policy supersedes obsolete probability/JEV usage; whether `it_status` remains a feature is unresolved.** |
| Golden ownership | Task asks P5 to publish `data/curated/curated_flat_golden_jobs.parquet`; P5 §1/§5 says P4 Golden is read-only and P5 must not modify it; current code does not write it. | **Unresolved decision; no P5 change to Golden without approval.** |
| Matrix filenames/schema | Task uses `skill_cooccurrence.parquet`; SPEC-06 names `matrix_skill_cooccurrence.parquet`; neither defines schema, labels or R2 layout. | **Unresolved decision.** |
| R2 export | Current `r2_export.GOLD_KEYS` exports only features/dictionary; task requires three/four more outputs. | **Current state gap; changing export architecture requires an approved artifact contract.** |
| Mining schemas | SPEC-07 conceptual requirements/reference prefixes, current P5 feature names, and SPEC-13 RF command input disagree. | **Unresolved cross-module interface.** |

## Implementation boundary

The approved 230-width decision is reflected throughout this contract, but it is insufficient to implement a vocabulary from the current 40-item taxonomy without further approval. Until the remaining unresolved decisions are approved, safe P5 work is limited to preserving the existing P5 input/output boundary, deterministic encoding behavior, row conservation, dictionary traceability, and offline tests. Creating or publishing TF-IDF, co-occurrence, a new Golden file, or selecting/expanding an altered 230-column vocabulary would change an unresolved interface and must be explicitly authorized.
