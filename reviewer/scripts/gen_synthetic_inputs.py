#!/usr/bin/env python3
"""Generate the three synthetic domain input files used by the reviewer route.

The original demonstration campaigns read three third-party datasets that
cannot be redistributed (see ``reviewer/fixtures/README.md``). This script
regenerates schema-identical, fully synthetic replacements from a fixed seed so
that any reviewer can reproduce byte-identical inputs without obtaining the
third-party sources.

No real person, patient, applicant, or employee is represented. All values are
drawn from fixed vocabularies and a seeded pseudo-random generator.

Usage:
    python3 reviewer/scripts/gen_synthetic_inputs.py [--out reviewer/fixtures]
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import random

SEED = 20261023

ADMISSIONS_HEADER = [
    "",
    "highschool",
    "URM",
    "satact",
    "GPA",
    "essayrating",
    "ecrating",
    "lor",
    "faaltu",
    "edaccept",
    "Did you get into your ED/REA college?",
    "acceptance",
    "attending",
    "Add. Info/Context ",
]

EHR_HEADER = [
    "patientunitstayid",
    "patienthealthsystemstayid",
    "gender",
    "age",
    "ethnicity",
    "hospitalid",
    "wardid",
    "apacheadmissiondx",
    "admissionheight",
    "hospitaladmittime24",
    "hospitaladmitoffset",
    "hospitaladmitsource",
    "hospitaldischargeyear",
    "hospitaldischargetime24",
    "hospitaldischargeoffset",
    "hospitaldischargelocation",
    "hospitaldischargestatus",
    "unittype",
    "unitadmittime24",
    "unitadmitsource",
    "unitvisitnumber",
    "unitstaytype",
    "admissionweight",
    "dischargeweight",
    "unitdischargetime24",
    "unitdischargeoffset",
    "unitdischargelocation",
    "unitdischargestatus",
    "uniquepid",
]

RETAIL_HEADER = ["Employee ID", "Store ID", "Name", "Position"]

SCHOOL_TYPES = [
    "Not a feeder, Private school",
    "Feeder, Public school",
    "Not a feeder, Public school",
    "Feeder, Private school",
    "Homeschool",
]
TEST_STATUS = ["Test Optional", "1450-1550", "1350-1440", "31-33 ACT", "34-36 ACT"]
GPA_BANDS = ["3.8+", "3.5-3.79", "3.2-3.49", "4.0 weighted"]
ED_COLLEGES = [
    "synthetic college a ED",
    "synthetic college b REA",
    "synthetic college c ED",
    "synthetic university d ED2",
]
ATTENDING = [
    "synthetic state university",
    "my ed school",
    "synthetic liberal arts college",
    "gap year",
]
CONTEXT_NOTES = [
    "first generation applicant, synthetic record",
    "applied for need-based aid, synthetic record",
    "recruited athlete track, synthetic record",
    "",
]

GENDERS = ["Male", "Female"]
ETHNICITIES = ["Caucasian", "African American", "Asian", "Hispanic", "Other/Unknown"]
ADMIT_DX = [
    "Hypertension, uncontrolled",
    "Sepsis, pulmonary",
    "Diabetic ketoacidosis",
    "Rhythm disturbance (atrial, supraventricular)",
    "Chest pain, unknown origin",
]
ADMIT_SOURCE = ["Direct Admit", "Emergency Department", "Floor", "Operating Room"]
UNIT_TYPES = ["Neuro ICU", "MICU", "SICU", "Cardiac ICU", "Med-Surg ICU"]
DISCHARGE_LOCATION = ["Home", "Skilled Nursing Facility", "Rehabilitation", "Floor"]
DISCHARGE_STATUS = ["Alive", "Expired"]

FIRST_NAMES = [
    "Avery", "Blake", "Casey", "Devon", "Emery", "Finley", "Gray", "Harper",
    "Indigo", "Jordan", "Kai", "Lennox", "Marlow", "Noel", "Oakley", "Peyton",
    "Quinn", "Reese", "Sage", "Tatum", "Umber", "Vale", "Wren", "Yael",
]
LAST_NAMES = [
    "Aldridge", "Bramley", "Castellan", "Denholm", "Eastwood", "Fairholm",
    "Garnier", "Halloway", "Ibsen", "Jarratt", "Kingsmill", "Lockhart",
    "Merriweather", "Norrington", "Oakhurst", "Pemberly", "Quillon",
    "Ravensworth", "Stallard", "Thackeray",
]
POSITIONS = [
    "Store Manager", "Assistant Manager", "Sales Associate", "Cashier",
    "Stock Clerk", "Visual Merchandiser", "Shift Supervisor",
]


def _time24(rng: random.Random) -> str:
    return f"{rng.randrange(24):02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}"


def write_admissions(path: pathlib.Path, rows: int, rng: random.Random) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(ADMISSIONS_HEADER)
        for index in range(rows):
            writer.writerow([
                index,
                rng.choice(SCHOOL_TYPES),
                rng.choice(["Yes", "No"]),
                rng.choice(TEST_STATUS),
                rng.choice(GPA_BANDS),
                rng.randrange(1, 11),
                rng.randrange(1, 11),
                rng.randrange(1, 6),
                rng.choice(["Yes (vibe check)", "No"]),
                rng.choice(ED_COLLEGES),
                rng.choice(["Yes", "No"]),
                rng.choice(["accepted", "rejected", "deferred", "waitlisted"]),
                rng.choice(ATTENDING),
                rng.choice(CONTEXT_NOTES),
            ])


def write_ehr(path: pathlib.Path, rows: int, rng: random.Random) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(EHR_HEADER)
        for index in range(rows):
            admit_offset = -rng.randrange(1, 600)
            discharge_offset = rng.randrange(600, 8000)
            writer.writerow([
                900000 + index,
                800000 + index,
                rng.choice(GENDERS),
                rng.randrange(18, 90),
                rng.choice(ETHNICITIES),
                rng.randrange(1, 200),
                rng.randrange(1, 400),
                rng.choice(ADMIT_DX),
                round(rng.uniform(150.0, 195.0), 1),
                _time24(rng),
                admit_offset,
                "",
                rng.randrange(2014, 2017),
                _time24(rng),
                discharge_offset,
                rng.choice(DISCHARGE_LOCATION),
                rng.choice(DISCHARGE_STATUS),
                rng.choice(UNIT_TYPES),
                _time24(rng),
                rng.choice(ADMIT_SOURCE),
                rng.randrange(1, 4),
                "admit",
                round(rng.uniform(50.0, 140.0), 1),
                round(rng.uniform(50.0, 140.0), 1),
                _time24(rng),
                discharge_offset,
                rng.choice(DISCHARGE_LOCATION),
                rng.choice(DISCHARGE_STATUS),
                f"synthetic-{index:06d}",
            ])


def write_retail(path: pathlib.Path, rows: int, rng: random.Random) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(RETAIL_HEADER)
        for index in range(1, rows + 1):
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            writer.writerow([index, rng.randrange(1, 41), name, rng.choice(POSITIONS)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="reviewer/fixtures")
    parser.add_argument(
        "--rows",
        type=int,
        default=12,
        help=(
            "rows per file. The default is deliberately small: the ingestion "
            "stage sends the whole file to a language model, and a local model "
            "takes minutes over a large batch."
        ),
    )
    args = parser.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    write_admissions(out / "admissiondata.csv", args.rows, rng)
    write_ehr(out / "EHR.csv", args.rows, rng)
    write_retail(out / "retail_employees.csv", args.rows, rng)

    for name in ("admissiondata.csv", "EHR.csv", "retail_employees.csv"):
        target = out / name
        print(f"wrote {target} ({target.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
