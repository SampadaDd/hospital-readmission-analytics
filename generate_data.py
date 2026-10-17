#!/usr/bin/env python3
"""
Generate realistic sample data for the hospital readmissions project.

Produces sql/02_sample_data.sql with:
  - 4 wards, 12 providers, ~600 patients, ~3,000 admissions
  - Spread across calendar year 2025
  - Built-in signal (so the analytics find something real):
      * ICU (ward 4) has the HIGHEST readmission tendency; Orthopedics (2) the lowest
      * Readmission gaps concentrated in the 5-30 day range for "readmitters"
      * A seasonal admissions bump in winter months
      * ~1% deliberately dirty rows (discharge before admission) to exercise
        the >= 0 data-quality guard
Deterministic (fixed seed) so the repo is reproducible.
"""
import random
from datetime import date, timedelta

random.seed(42)

START = date(2025, 1, 1)
END   = date(2025, 12, 31)
N_PATIENTS   = 2200   # more patients, each with few visits -> readmissions are
N_ADMISSIONS = 3000   #   a designed signal, not random same-patient overlap

WARDS = [
    (1, "Cardiology",  40),
    (2, "Orthopedics", 30),
    (3, "General Med", 60),
    (4, "ICU",         20),
]
# Per-ward probability that a discharged patient is readmitted within 30 days.
WARD_READMIT_P = {1: 0.14, 2: 0.06, 3: 0.18, 4: 0.30}
# Per-ward typical length of stay (days) as (min, max).
WARD_LOS = {1: (3, 10), 2: (2, 7), 3: (3, 12), 4: (5, 18)}

PROVIDERS = [
    (1, "Dr. Lee",      "Cardiologist",       1),
    (2, "Dr. Alvarez",  "Cardiologist",       1),
    (3, "Dr. Patel",    "Orthopedic Surgeon", 2),
    (4, "Dr. Weber",    "Orthopedic Surgeon", 2),
    (5, "Dr. Okafor",   "Internist",          3),
    (6, "Dr. Rossi",    "Internist",          3),
    (7, "Dr. Haddad",   "Internist",          3),
    (8, "Dr. Nguyen",   "Intensivist",        4),
    (9, "Dr. Johnson",  "Intensivist",        4),
    (10,"Dr. Kim",      "Hospitalist",        3),
    (11,"Dr. Santos",   "Cardiologist",       1),
    (12,"Dr. Brown",    "Hospitalist",        3),
]
PROVIDERS_BY_WARD = {}
for pid, name, spec, ward in PROVIDERS:
    PROVIDERS_BY_WARD.setdefault(ward, []).append(pid)

REASONS = {
    1: ["Chest pain", "Heart failure", "Arrhythmia", "Angina", "Hypertensive crisis"],
    2: ["Hip fracture", "Knee replacement", "Spinal fusion", "Fracture", "Joint infection"],
    3: ["Pneumonia", "Infection", "Diabetic crisis", "Cellulitis", "Fluid overload", "Sepsis"],
    4: ["Respiratory failure", "Septic shock", "Post-op monitoring", "Cardiac arrest", "Trauma"],
}

FIRST = ["Maria","James","Aisha","Robert","Linda","Wei","Sofia","David","Grace","Omar",
         "Nina","Carlos","Fatima","John","Priya","Hassan","Elena","Marcus","Yuki","Ana",
         "Tariq","Mei","Diego","Sarah","Kwame","Ingrid","Raj","Chloe","Ivan","Amara"]
LAST  = ["Gomez","Carter","Khan","Smith","Johnson","Chen","Rodriguez","Brown","Park","Haddad",
         "Petrova","Silva","Ali","Nguyen","Patel","Osei","Rossi","Lee","Tanaka","Costa",
         "Kim","Dubois","Martin","Weber","Ibrahim","Larsson","Mehta","Flores","Novak","Diallo"]
STREETS = ["Oak St","Pine Ave","Maple Rd","Elm Blvd","Birch Ln","Cedar Ct","Walnut St",
           "Ash Dr","Spruce Way","Poplar St","Willow Dr","Cherry Ln"]

def rand_date(a, b):
    return a + timedelta(days=random.randint(0, (b - a).days))

# ---- patients ----
patients = []
for pid in range(1, N_PATIENTS + 1):
    name = f"{random.choice(FIRST)} {random.choice(LAST)}"
    dob = rand_date(date(1935, 1, 1), date(2005, 1, 1))
    addr = f"{random.randint(1,999)} {random.choice(STREETS)}"
    # ~60% have a medicare id (older patients more likely)
    medicare = f"MC{100000+pid}" if (dob.year < 1965 or random.random() < 0.4) else None
    patients.append((pid, name.replace("'", "''"), dob, addr, medicare))

# ---- admissions ----
admissions = []
aid = 0
# Give each admission a ward with weighting toward General Med (biggest),
# then build its stay, then possibly a readmission chain.
def new_admission(pid, ward, adm_date):
    global aid
    aid += 1
    lo, hi = WARD_LOS[ward]
    los = random.randint(lo, hi)
    dis_date = adm_date + timedelta(days=los)
    prov = random.choice(PROVIDERS_BY_WARD[ward])
    reason = random.choice(REASONS[ward])
    admissions.append([aid, pid, ward, prov, adm_date, dis_date, reason])
    return dis_date

def seasonal_date():
    # seasonal weighting: more admissions in winter (Jan-Mar, Nov-Dec)
    for _ in range(10):
        adm = rand_date(START, END - timedelta(days=40))
        if adm.month in (1, 2, 3, 11, 12) or random.random() < 0.5:
            return adm
    return adm

ward_pool = [1]*22 + [2]*16 + [3]*40 + [4]*22  # relative admission frequency

# Each patient gets ONE index admission. With the ward's probability it is
# followed by a readmission within 5-30 days (the designed signal). Repeat,
# UNRELATED visits are rare and deliberately placed >120 days later so they
# never masquerade as readmissions.
pid_cycle = list(range(1, N_PATIENTS + 1))
random.shuffle(pid_cycle)
i = 0
while len(admissions) < N_ADMISSIONS:
    pid = pid_cycle[i % N_PATIENTS]
    i += 1
    ward = random.choice(ward_pool)
    adm = seasonal_date()
    dis = new_admission(pid, ward, adm)

    # designed readmission within 30 days (ward-driven)
    if random.random() < WARD_READMIT_P[ward] and len(admissions) < N_ADMISSIONS:
        gap = random.randint(5, 30)
        re_adm = dis + timedelta(days=gap)
        if re_adm <= END - timedelta(days=5):
            re_ward = ward if random.random() < 0.6 else 3
            new_admission(pid, re_ward, re_adm)

    # rare unrelated later visit, placed far away so it is NOT a readmission
    if random.random() < 0.04 and len(admissions) < N_ADMISSIONS:
        far = dis + timedelta(days=random.randint(120, 300))
        if far <= END - timedelta(days=5):
            new_admission(pid, random.choice(ward_pool), far)

# ---- inject ~1% dirty rows (discharge BEFORE admission) ----
n_dirty = max(1, len(admissions)//100)
for row in random.sample(admissions, n_dirty):
    # swap so discharge precedes admission -> negative gap if used naively
    row[4], row[5] = row[5], row[4]

random.shuffle(admissions)
for i, row in enumerate(admissions, start=1):
    row[0] = i  # renumber admission_id sequentially after shuffle

# ---- emit SQL ----
def q(v):
    return "NULL" if v is None else f"'{v}'"

lines = []
lines.append("-- ============================================================")
lines.append("-- Hospital Readmissions Analytics - Sample Data (GENERATED)")
lines.append(f"-- {len(patients)} patients, {len(admissions)} admissions, "
             "calendar year 2025.")
lines.append("-- Generated by generate_data.py (seed=42, reproducible).")
lines.append("-- Signal built in: ICU has the highest readmission rate,")
lines.append("-- Orthopedics the lowest; ~1% dirty rows (discharge<admission)")
lines.append("-- to exercise the >= 0 data-quality guard.")
lines.append("-- ============================================================\n")

lines.append("INSERT INTO wards (ward_number, ward_name, total_capacity) VALUES")
lines.append(",\n".join(f"    ({w}, '{n}', {c})" for w, n, c in WARDS) + ";\n")

lines.append("INSERT INTO providers (provider_id, provider_name, specialty) VALUES")
lines.append(",\n".join(f"    ({p}, '{n}', '{s}')" for p, n, s, _ in PROVIDERS) + ";\n")

lines.append("INSERT INTO patients (patient_id, patient_name, patient_dob, address, medicare_id) VALUES")
prows = [f"    ({pid}, '{name}', '{dob}', '{addr}', {q(mc)})"
         for pid, name, dob, addr, mc in patients]
lines.append(",\n".join(prows) + ";\n")

lines.append("INSERT INTO admissions (admission_id, patient_id, ward_number, provider_id, "
             "admission_date, discharge_date, reason_for_admission) VALUES")
arows = [f"    ({a}, {p}, {w}, {pr}, '{adm}', '{dis}', '{r}')"
         for a, p, w, pr, adm, dis, r in admissions]
lines.append(",\n".join(arows) + ";")

with open("sql/02_sample_data.sql", "w") as f:
    f.write("\n".join(lines) + "\n")

print(f"Wrote sql/02_sample_data.sql: {len(patients)} patients, "
      f"{len(admissions)} admissions, {n_dirty} dirty rows")
