# Domain inputs for the reviewer route

## Summary

The three domain input files that the demonstration campaigns read are
third-party datasets containing person-level records. They are **not**
redistributable, and this repository does not ship them. The reviewer route
instead ships schema-identical synthetic replacements that are regenerated
deterministically by `reviewer/scripts/gen_synthetic_inputs.py`.

This decision is recorded here because the four-page paper states that the
release does not ship the domain input files, and a reviewer needs to know why
and what replaces them.

## Audit of the original inputs

| Original file | Domain | Rows (excl. header) | Provenance | Personal data | Licence position | Release decision |
|---|---|---:|---|---|---|---|
| `admissiondata.csv` | university admissions | 102 | Third-party dataset of self-reported college-admission outcomes redistributed on a public data platform. No licence file accompanied the local copy. | Free-text `Add. Info/Context` column carrying self-reported personal circumstances; `URM` records a protected attribute. | Unverified. No upstream licence or terms were retained with the file. | **Not released.** |
| `EHR.csv` | healthcare | 1,446 | Column set matches the `patient` table of a critical-care research database distributed under credentialed access. | Patient-level demographics, admission diagnosis, physical measurements, unit stay, and discharge status. | Credentialed-access data use agreements for that database prohibit redistribution. | **Not released.** |
| `retail_employees.csv` | retail | 404 | Third-party retail dataset redistributed on a public data platform; the associated customer file carries names, emails, telephone numbers, and dates of birth. | Employee names paired with store assignment and role. | Unverified. No upstream licence or terms were retained with the file. | **Not released.** |

Two further points follow from this audit and are stated in the paper's
limitations rather than being repaired here:

1. The original inputs are described as synthetic in the demonstration
   narrative, but at least the healthcare file derives from a real clinical
   research corpus. Only the *telemetry* the mock generator emits is synthetic;
   the seed records were not.
2. No schema documentation accompanied the files in the released package, so a
   reviewer could not previously reconstruct a compatible input.

## What ships instead

`reviewer/fixtures/` contains three files with identical column names and
column order, generated from a fixed seed (`20261023`) by
`reviewer/scripts/gen_synthetic_inputs.py`. Every value is drawn from a fixed
vocabulary or a seeded pseudo-random generator. No real person, patient,
applicant, or employee is represented, and no value is derived from the
original files.

Each file ships with **12 rows**, not the original row counts. The ingestion
stage aggregates a whole file into a single language-model prompt, and the
reviewer route runs that model locally, so a 1,446-row file would take a small
local model hours. Row count does not affect which code paths execute.

Regenerate them at any time, at any size:

```bash
python3 reviewer/scripts/gen_synthetic_inputs.py --out reviewer/fixtures
python3 reviewer/scripts/gen_synthetic_inputs.py --out reviewer/fixtures --rows 250
```

The files are mounted read-only into the n8n container at
`/home/node/.n8n-files/`, which is the path the workflow's file-reader nodes
already used.

### `admissiondata.csv`

| Column | Type | Notes |
|---|---|---|
| (unnamed first column) | integer | row index, present in the original schema |
| `highschool` | string | school-type description |
| `URM` | `Yes`/`No` | synthetic protected-attribute flag |
| `satact` | string | test-score band or `Test Optional` |
| `GPA` | string | grade band |
| `essayrating`, `ecrating` | integer 1–10 | self-rated components |
| `lor` | integer 1–5 | letters of recommendation |
| `faaltu` | string | free-text flag retained from the original schema |
| `edaccept` | string | early-decision target, synthetic institution names |
| `Did you get into your ED/REA college?` | `Yes`/`No` | |
| `acceptance` | string | outcome |
| `attending` | string | synthetic institution name |
| `Add. Info/Context ` | string | short synthetic note; trailing space in the header is preserved |

### `EHR.csv`

Twenty-nine columns matching the original header exactly, covering unit-stay
identifiers, demographics, admission diagnosis, admission and discharge times
and offsets, unit type, weights, and discharge status. Identifiers are
sequential (`900000+`), and `uniquepid` values take the form
`synthetic-000000`.

### `retail_employees.csv`

| Column | Type | Notes |
|---|---|---|
| `Employee ID` | integer | sequential |
| `Store ID` | integer 1–40 | |
| `Name` | string | first and last name drawn from fixed synthetic vocabularies |
| `Position` | string | retail role |

## Effect on the demonstration

The stage structure, prompts, ontology writes, and stored schemas are
unchanged, so the five stages exercise the same code paths. The generated
content differs from the campaign outputs, and nothing produced from these
fixtures reproduces the reported campaign numbers or constitutes a validated
privacy assessment.
