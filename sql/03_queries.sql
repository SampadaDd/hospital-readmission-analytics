-- ============================================================
-- Hospital Readmissions Analytics — Queries 1–9
-- ============================================================
-- Dialect: PostgreSQL.
--   Date difference in Postgres:  (end_date - start_date)  -> integer days.
--   MySQL equivalent:             DATEDIFF(end_date, start_date)
--   Next-day in Postgres:         day + INTERVAL '1 day'
--   MySQL equivalent:             DATE_ADD(day, INTERVAL 1 DAY)
-- ============================================================


-- ------------------------------------------------------------
-- Q1. JOIN warm-up
-- "List every admission with the patient's name, ward, and dates —
--  most recent admission first."
-- Concept: INNER JOIN across tables, named columns, ORDER BY DESC.
-- ------------------------------------------------------------
SELECT  p.patient_name,
        a.ward_number,
        a.admission_date,
        a.discharge_date
FROM    admissions a
JOIN    patients p ON a.patient_id = p.patient_id
ORDER BY a.admission_date DESC;


-- ------------------------------------------------------------
-- Q2. GROUP BY / COUNT / HAVING
-- "How many admissions has each ward had — only wards with more
--  than 100, busiest first."
-- Concept: aggregation that COLLAPSES rows; WHERE filters rows,
-- HAVING filters groups (COUNT doesn't exist until after grouping).
-- ------------------------------------------------------------
SELECT    ward_number,
          COUNT(admission_id) AS admission_count
FROM      admissions
GROUP BY  ward_number
HAVING    COUNT(admission_id) > 100
ORDER BY  admission_count DESC;


-- ------------------------------------------------------------
-- Q3. First window function — COUNT ... OVER (PARTITION BY ...)
-- "Show every admission, tagged with the total admissions in its ward."
-- Concept: a window function is like GROUP BY but it KEEPS every row
-- and writes the group value next to each one (annotate, don't collapse).
-- ------------------------------------------------------------
SELECT  admission_id,
        ward_number,
        COUNT(*) OVER (PARTITION BY ward_number) AS ward_total_admissions
FROM    admissions
ORDER BY ward_number, admission_id;


-- ------------------------------------------------------------
-- Q4. ROW_NUMBER — sequence each patient's admissions
-- "Number each patient's admissions chronologically (1st, 2nd, 3rd)."
-- Concept: PARTITION BY restarts the counter per patient;
-- ORDER BY decides who is #1 (earliest).
-- ------------------------------------------------------------
SELECT  patient_id,
        admission_id,
        admission_date,
        ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY admission_date) AS admission_seq
FROM    admissions
ORDER BY patient_id, admission_seq;


-- ------------------------------------------------------------
-- Q5. LEAD — pull the next admission's date onto the current row
-- "For each admission, show when that patient's NEXT admission was."
-- Concept: LEAD reads the next row in order (it reads already-written
-- history, it does not predict). NULL = no later admission on record.
-- ------------------------------------------------------------
SELECT  patient_id,
        admission_id,
        admission_date,
        discharge_date,
        LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
FROM    admissions
ORDER BY patient_id, admission_date;


-- ------------------------------------------------------------
-- Q6. SHOWPIECE #1 — 30-day readmission flag
-- "Flag each admission that was followed by a readmission within 30 days."
-- Concept: multi-layer CTE. LEAD -> date math -> CASE flag.
-- Guard is (gap >= 0 AND gap <= 30): <= 30 is the window, >= 0 rejects
-- impossible negative gaps from dirty data. (Same-day return counts here
-- as a readmission; use "> 0" if the business treats it as a transfer.)
-- ------------------------------------------------------------
WITH step1 AS (
    SELECT  patient_id,
            admission_id,
            ward_number,
            discharge_date,
            LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
    FROM    admissions
),
step2 AS (
    SELECT  patient_id,
            admission_id,
            ward_number,
            discharge_date,
            next_admission_date,
            (next_admission_date - discharge_date) AS days_to_readmission   -- MySQL: DATEDIFF(next_admission_date, discharge_date)
    FROM    step1
)
SELECT  patient_id,
        admission_id,
        discharge_date,
        next_admission_date,
        days_to_readmission,
        CASE WHEN days_to_readmission >= 0 AND days_to_readmission <= 30
             THEN 1 ELSE 0 END AS is_readmission_30d
FROM    step2
ORDER BY patient_id, discharge_date;


-- ------------------------------------------------------------
-- Q7. SHOWPIECE support — RANK wards by readmission rate
-- "Which wards have the worst 30-day readmission rate?"
-- Concept: aggregate a 0/1 flag -> rate = SUM(flag)/COUNT(*).
-- SUM counts the 1s (readmissions); COUNT counts all rows (total).
-- *1.0 forces decimal division; *100 makes it a percentage.
-- Then RANK() orders wards worst-first.
-- ------------------------------------------------------------
WITH flagged AS (
    SELECT  a.admission_id,
            a.ward_number,
            CASE WHEN (nxt.next_admission_date - a.discharge_date) >= 0
                  AND (nxt.next_admission_date - a.discharge_date) <= 30
                 THEN 1 ELSE 0 END AS is_readmission_30d
    FROM    admissions a
    JOIN    (
        SELECT  admission_id,
                LEAD(admission_date) OVER (PARTITION BY patient_id ORDER BY admission_date) AS next_admission_date
        FROM    admissions
    ) nxt ON a.admission_id = nxt.admission_id
),
ward_stats AS (
    SELECT  ward_number,
            COUNT(*)                        AS total_admissions,
            SUM(is_readmission_30d)         AS readmissions,
            SUM(is_readmission_30d) * 100.0 / COUNT(*) AS readmission_rate_pct
    FROM    flagged
    GROUP BY ward_number
)
SELECT  ward_number,
        total_admissions,
        readmissions,
        ROUND(readmission_rate_pct, 1) AS readmission_rate_pct,
        RANK() OVER (ORDER BY readmission_rate_pct DESC) AS ward_rank
FROM    ward_stats
ORDER BY ward_rank;


-- ------------------------------------------------------------
-- Q8. Frame clauses — running total & 7-day moving average
-- "Cumulative admissions over time, plus a 7-day moving average."
-- Concept: the frame clause ROWS BETWEEN ... AND ... sets which rows
-- around the current one feed the calculation.
--   running total  = UNBOUNDED PRECEDING .. CURRENT ROW  (window grows)
--   7-day moving   = 6 PRECEDING .. CURRENT ROW          (fixed slide;
--                    6 + current = 7 rows)
-- No PARTITION BY = one continuous calculation across the whole hospital.
-- ------------------------------------------------------------
WITH daily AS (
    SELECT  admission_date,
            COUNT(*) AS daily_admissions
    FROM    admissions
    GROUP BY admission_date
)
SELECT  admission_date,
        daily_admissions,
        SUM(daily_admissions) OVER (ORDER BY admission_date
                                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total,
        ROUND(AVG(daily_admissions) OVER (ORDER BY admission_date
                                    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)     AS moving_avg_7day
FROM    daily
ORDER BY admission_date;


-- ------------------------------------------------------------
-- Q9. SHOWPIECE #2 — bed occupancy via interval overlap
-- "How many beds were occupied on each day?"
-- Concept: an admission is an INTERVAL [admission_date, discharge_date].
-- A day X is occupied by it when  X >= admission_date AND X <= discharge_date
-- (interval-contains-a-point test; a NON-EQUI JOIN, on >= and <= not =).
--
-- The day-list is a DATE SPINE built with a recursive CTE so EVERY
-- calendar day appears — including quiet days when nobody new arrived
-- but patients were still in beds. LEFT JOIN + COUNT(column) keeps those
-- days and reports 0 (plain JOIN would drop them; COUNT(*) would wrongly
-- show 1 for an empty day).
-- MySQL: use WITH RECURSIVE too; next day = DATE_ADD(day, INTERVAL 1 DAY).
-- ------------------------------------------------------------
WITH RECURSIVE date_spine AS (
    SELECT MIN(admission_date) AS day          -- anchor: first day in range
    FROM   admissions
    UNION ALL
    SELECT (day + INTERVAL '1 day')::date      -- recursive step: +1 day
    FROM   date_spine                          -- (cast back to DATE: in Postgres
                                               --  date + interval yields a timestamp)
    WHERE  day < (SELECT MAX(discharge_date) FROM admissions)   -- stop at last discharge
)
SELECT  d.day AS day,
        COUNT(a.admission_id) AS beds_occupied
FROM    date_spine d
LEFT JOIN admissions a
       ON  d.day >= a.admission_date
       AND d.day <= a.discharge_date
GROUP BY d.day
ORDER BY d.day;
