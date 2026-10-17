# Hospital Readmissions SQL — Learning & Teaching Notes

This is the full walkthrough of the project: the business problem, how the
schema was reasoned out, and every query built up from simple to advanced —
each with the guiding questions, the reasoning, the code, and the interview
follow-ups. It's written so you can **explain the whole thing to someone else**.

---

## Part 1 — The business problem

Hospitals get financially penalized when a patient is readmitted within 30 days
of discharge (US Medicare's Hospital Readmissions Reduction Program). It costs
real money and signals quality problems. Bed capacity is a second constant
pressure — you can't staff or plan if you can't see occupancy.

Three questions drive everything:
1. Which admissions were followed by a 30-day readmission?
2. Which wards have the worst readmission rates?
3. How full were the beds on each day?

---

## Part 2 — Designing the schema (the part interviewers test first)

**The single most important decision: what does one row represent?**

Tempting answer: one row = one patient. That breaks immediately. Take a patient
with two visits (January pneumonia, March hip fracture). If she's one row, where
does the second visit's dates go? And the whole question — "was she readmitted?"
— is *about the relationship between two visits*. If she's one row, there's
nothing to compare.

**So: one row = one admission (one visit).** Now she has two rows, both pointing
back to her, and "did she come back within 30 days?" becomes answerable.

That decision ripples outward. Four principles came out of it:

- **Store facts, derive relationships.** Don't store "previous admission" on a
  row. Each admission stores only *its own* dates. The 30-day relationship is
  *computed later* (with `LEAD`), not stored.
- **Foreign key = a column holding another table's primary key value.** Test:
  can you point at the table whose PK it matches? If not, it's a plain
  attribute. `medicare_id` points at no table → it's an attribute of the
  patient, not a foreign key.
- **Model what the questions require, not every true fact.** A patient really
  does have insurance coverage tiers and benefits — but no question here reads
  them, so no coverage table is built. (Skis don't go in a beach-trip suitcase.)
  You add structure when a question demands it.
- **A foreign key goes on the "many" side, pointing at the "one" side.** A ward
  has many patients, so `patient_id` does NOT go in `wards`. The link already
  lives in `admissions` (one row = one patient in one ward).

Final schema:

```
patients   (patient_id PK, patient_name, patient_dob, address, medicare_id)
wards      (ward_number PK, ward_name, total_capacity)
providers  (provider_id PK, provider_name, specialty)
admissions (admission_id PK, patient_id FK, ward_number FK, provider_id FK,
            admission_date, discharge_date, reason_for_admission)
```

---

## Part 3 — The queries, simple to advanced

### The one mental model for window functions

A window function is **like `GROUP BY`, but it keeps every row.** `GROUP BY`
collapses many rows into one summary row. A window function does the same kind
of calculation but writes the answer *next to each row* — every row survives,
now tagged with its group's (or neighbor's) context. Everything below
(`ROW_NUMBER`, `LEAD`, `RANK`, running totals) is a flavor of that.

Inside `OVER (...)` there are two controls:
- `PARTITION BY` — which group to calculate within (the cousin of `GROUP BY`).
  No `PARTITION BY` = one calculation across everything.
- `ORDER BY` — the order of rows within the group (needed for anything that
  depends on sequence: running totals, `LEAD`/`LAG`, `ROW_NUMBER`).

---

### Q1 — JOIN warm-up

**Question:** List every admission with the patient's name, ward, and dates;
most recent first.

**Guiding questions:** The patient's *name* lives in `patients`, but the
admission lives in `admissions`. What connects two tables on a shared key?
Which column do they share? Which clause sorts, and which direction is "newest
first"?

**Reasoning:** Name isn't in `admissions`, so you `JOIN` to `patients` on the
shared `patient_id`. Name the columns you want (not `SELECT *`). `DESC` puts the
newest date on top.

```sql
SELECT  p.patient_name, a.ward_number, a.admission_date, a.discharge_date
FROM    admissions a
JOIN    patients p ON a.patient_id = p.patient_id
ORDER BY a.admission_date DESC;
```

---

### Q2 — GROUP BY / COUNT / HAVING

**Question:** How many admissions per ward? Only wards above a threshold.
Busiest first.

**Guiding questions:** "How many per ward" — what clause groups rows so you can
count within each? "Only wards above N" — you're filtering on a *count*, which
doesn't exist until after grouping. Which keyword filters *after* grouping?

**Reasoning:** `GROUP BY` collapses to one row per ward. The crucial distinction:
**`WHERE` filters individual rows *before* grouping; `HAVING` filters groups
*after*.** You can't use `WHERE COUNT(...) > N` because the count doesn't exist
yet when `WHERE` runs. Clause order is fixed:
`SELECT → FROM → WHERE → GROUP BY → HAVING → ORDER BY`.

```sql
SELECT    ward_number, COUNT(admission_id) AS admission_count
FROM      admissions
GROUP BY  ward_number
HAVING    COUNT(admission_id) > 3
ORDER BY  admission_count DESC;
```

---

### Q3 — First window function

**Question:** Show every admission, tagged with the total admissions in its
ward. (Unlike Q2, keep every row.)

**Reasoning:** `GROUP BY` would collapse the rows. You want to *annotate*, not
collapse — so `COUNT(*) OVER (PARTITION BY ward_number)`: count per ward, stamp
it on every row of that ward. Always alias the computed column.

```sql
SELECT  admission_id, ward_number,
        COUNT(*) OVER (PARTITION BY ward_number) AS ward_total_admissions
FROM    admissions;
```

---

### Q4 — ROW_NUMBER

**Question:** Number each patient's admissions chronologically (1st, 2nd, 3rd).

**Guiding questions:** The counter should restart for each new patient — so
partition by what? Within a patient, the earliest visit is #1 — so order by what,
in which direction?

**Reasoning:** `PARTITION BY patient_id` restarts the count per patient;
`ORDER BY admission_date ASC` makes the earliest #1. This builds the sequence
that readmission logic rides on.

```sql
SELECT  patient_id, admission_id, admission_date,
        ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY admission_date) AS admission_seq
FROM    admissions;
```

---

### Q5 — LEAD (peek at the next row)

**Question:** For each admission, show when that patient's *next* admission was.

**Key idea:** `LEAD(col)` pulls a value from the **next** row in order;
`LAG(col)` from the **previous** row. "Next" only means something once rows are
ordered — so these always need `ORDER BY`, usually with `PARTITION BY` so one
patient's "next" doesn't bleed into another's.

**A conceptual point students get stuck on:** this is not prediction. When the
query runs, the whole table already exists. Reading the "next" admission is like
reading tomorrow's entry in a diary that's already fully written — not
forecasting. For a patient with no later visit, `LEAD` returns `NULL` (no
readmission on record — correct).

```sql
SELECT  patient_id, admission_id, admission_date, discharge_date,
        LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
FROM    admissions;
```

---

### Q6 — SHOWPIECE #1: the 30-day readmission flag

**Question:** Flag each admission that was followed by a readmission within 30
days.

**Guiding questions:** You now have `discharge_date` and `next_admission_date`
on the same row. What do you *calculate* from them, and what do you *compare*
it to? And — can you use a column you just created (`next_admission_date`)
inside the *same* `SELECT`?

**Reasoning, three parts:**

1. **The test:** days between discharge and next admission, `<= 30`. Anchor on
   the **discharge** date, not admission-to-admission — the clock starts when
   the patient *leaves*. (Example: a 40-day stay then a return 5 days later is a
   readmission, even though admission-to-admission is 45 days.)

2. **Why a CTE:** you can't reference a column alias inside the same `SELECT`
   that creates it — all columns in a `SELECT` are computed together, so the
   alias doesn't exist yet. A **CTE** (`WITH`) computes a result in one layer so
   the next layer can use it. Chain multiple CTEs with **one `WITH` + commas**
   (not repeated `WITH`), and no trailing comma before `FROM`.

3. **The data-quality guard:** the condition is `days >= 0 AND days <= 30`. The
   `<= 30` is the window; the `>= 0` rejects negative gaps that dirty data
   produces (a flipped date, an overlapping transfer). A plain `DATEDIFF` arg
   flip gives negatives *with no error* — the dangerous kind of bug. (Same-day
   return, `= 0`, counts here; a hospital treating it as a transfer would use
   `> 0`.)

```sql
WITH step1 AS (
    SELECT patient_id, admission_id, discharge_date,
           LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
    FROM   admissions
),
step2 AS (
    SELECT patient_id, admission_id, discharge_date, next_admission_date,
           (next_admission_date - discharge_date) AS days_to_readmission  -- MySQL: DATEDIFF(next_admission_date, discharge_date)
    FROM   step1
)
SELECT patient_id, admission_id, discharge_date, next_admission_date, days_to_readmission,
       CASE WHEN days_to_readmission >= 0 AND days_to_readmission <= 30
            THEN 1 ELSE 0 END AS is_readmission_30d
FROM   step2;
```

---

### Q7 — SHOWPIECE support: RANK wards by readmission rate

**Question:** Which wards have the worst readmission rates?

**Guiding questions:** What *is* a ward's readmission rate, in plain arithmetic?
If each row carries a 0/1 flag, how do you turn those into a rate? Which
function counts just the 1s?

**The key lesson:** `SUM(flag)` counts the 1s (readmissions); `COUNT(flag)` /
`COUNT(*)` counts all rows (total). So
`rate = SUM(is_readmission_30d) / COUNT(*)`. Multiply by `100.0` to force
decimal division (integer `15/100` truncates to `0`) and make it a percentage.
Then `RANK() OVER (ORDER BY rate DESC)` puts the worst ward first.

This **"aggregate a 0/1 flag"** pattern is one of the most reused moves in
analytics — conversion rates, churn, pass rates all have this exact shape.

```sql
WITH flagged AS (
    SELECT a.admission_id, a.ward_number,
           CASE WHEN (nxt.next_admission_date - a.discharge_date) >= 0
                 AND (nxt.next_admission_date - a.discharge_date) <= 30
                THEN 1 ELSE 0 END AS is_readmission_30d
    FROM   admissions a
    JOIN  (SELECT admission_id,
                  LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
           FROM admissions) nxt ON a.admission_id = nxt.admission_id
),
ward_stats AS (
    SELECT ward_number,
           COUNT(*)                AS total_admissions,
           SUM(is_readmission_30d) AS readmissions,
           SUM(is_readmission_30d) * 100.0 / COUNT(*) AS readmission_rate_pct
    FROM   flagged
    GROUP BY ward_number
)
SELECT ward_number, total_admissions, readmissions,
       ROUND(readmission_rate_pct, 1) AS readmission_rate_pct,
       RANK() OVER (ORDER BY readmission_rate_pct DESC) AS ward_rank
FROM   ward_stats
ORDER BY ward_rank;
```

*RANK vs DENSE_RANK vs ROW_NUMBER:* on a tie, `RANK` skips the next value
(1,1,3), `DENSE_RANK` doesn't (1,1,2), `ROW_NUMBER` breaks ties arbitrarily
(1,2,3). Good follow-up to have an answer ready for.

---

### Q8 — Frame clauses: running total & moving average

**Question:** Cumulative admissions over time, plus a 7-day moving average.

**Key idea:** the **frame clause** `ROWS BETWEEN ... AND ...` tells a window
function *which rows around the current one* to include.
- Running total: `ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — the window
  grows from the start.
- 7-day moving average: `ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` — a fixed
  sliding window. **6 preceding + the current row = 7 rows** (the off-by-one to
  watch).

No `PARTITION BY` here — one continuous calculation across the whole hospital.
(The frame keywords are fixed phrases; `CURRENT ROW` is not a column. `ORDER BY`
sets the order, the frame sets the window within it.)

```sql
WITH daily AS (
    SELECT admission_date, COUNT(*) AS daily_admissions
    FROM   admissions
    GROUP BY admission_date
)
SELECT admission_date, daily_admissions,
       SUM(daily_admissions) OVER (ORDER BY admission_date
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
       ROUND(AVG(daily_admissions) OVER (ORDER BY admission_date
             ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)     AS moving_avg_7day
FROM   daily
ORDER BY admission_date;
```

---

### Q9 — SHOWPIECE #2: bed occupancy (interval overlap)

**Question:** How many beds were occupied on each day?

**Why it's the hard one:** every earlier query treated an admission as an event
at a point. But an admission is an **interval** — it covers every day from
admission to discharge. "How full were we on day X?" = count every admission
whose interval *contains* X.

**The overlap test:** day X is inside a stay `[A, D]` when `X >= A AND X <= D`.
(Not `IN` — that's list membership; this is a range comparison.) Joining on
`>=`/`<=` instead of `=` is a **non-equi join**.

**Where do the days come from?** You need a row per day. Using only
`DISTINCT admission_date` is a trap: it misses quiet days when nobody new was
admitted but patients were still in beds — those days vanish from the output.
The fix is a **date spine**: a complete list of every calendar day in the range,
built with a **recursive CTE**.

A recursive CTE has three parts: an **anchor** (the first day), a **recursive
step** (previous day + 1, referencing the CTE itself), and a **stop condition**
(`WHERE day < max`). Note `day < max`, not `<=`: the row you're testing decides
whether to make the *next* one, so you stop one before the max (the max itself
was already created on the previous step).

**Last detail:** use `LEFT JOIN` + `COUNT(a.admission_id)`, not `JOIN` +
`COUNT(*)`. A plain `JOIN` drops days with zero matches (reintroducing the bug);
`LEFT JOIN` keeps them, and `COUNT(column)` returns `0` for them (whereas
`COUNT(*)` would wrongly return `1` for the empty row). This "keep empty buckets
and count them as zero" is itself a widely reused pattern.

```sql
WITH RECURSIVE date_spine AS (
    SELECT MIN(admission_date) AS day FROM admissions         -- anchor
    UNION ALL
    SELECT (day + INTERVAL '1 day')::date                     -- +1 day (cast to DATE in Postgres)
    FROM   date_spine
    WHERE  day < (SELECT MAX(discharge_date) FROM admissions) -- stop
)
SELECT d.day AS day,
       COUNT(a.admission_id) AS beds_occupied
FROM   date_spine d
LEFT JOIN admissions a
       ON d.day >= a.admission_date
      AND d.day <= a.discharge_date
GROUP BY d.day
ORDER BY d.day;
```

---

## Part 4 — The complete skill map

Joins · aliases · named columns · sorting · `GROUP BY`/`COUNT`/`HAVING` ·
`WHERE` vs `HAVING` · window functions (PARTITION-only, `ROW_NUMBER`,
`LEAD`/`LAG`, `RANK`, frame clauses) · multi-layer CTEs · recursive CTEs ·
`CASE` · date arithmetic · the `SUM(flag)/COUNT(*)` rate pattern · non-equi
joins · interval overlap · data-quality defensiveness.

That's the full toolkit that "advanced" data-science SQL interviews test.
