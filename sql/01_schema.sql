-- ============================================================
-- Hospital Readmissions Analytics — Schema
-- ============================================================
-- One row = one ADMISSION (a single hospital visit), which is
-- what makes "was the patient readmitted within 30 days?"
-- answerable: a patient with two visits has two rows to compare.
--
-- Dialect: PostgreSQL. MySQL differences are noted in comments.
-- ============================================================

DROP TABLE IF EXISTS admissions;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS wards;
DROP TABLE IF EXISTS providers;

-- Patients: one row per person. Stable facts that never change
-- between visits live here (name, DOB), so they are not duplicated
-- onto every admission.
CREATE TABLE patients (
    patient_id   INT PRIMARY KEY,
    patient_name VARCHAR(100) NOT NULL,
    patient_dob  DATE,
    address      VARCHAR(200),
    medicare_id  VARCHAR(20)      -- a plain attribute (an external ID),
                                  -- NOT a foreign key: it points at no table
);

-- Wards: one row per ward. total_capacity is a STABLE fact.
-- "beds available" is deliberately NOT stored — it is derived from
-- how many admissions overlap a given day (see 02_queries query 9).
CREATE TABLE wards (
    ward_number    INT PRIMARY KEY,
    ward_name      VARCHAR(50),
    total_capacity INT
);

-- Providers: one row per doctor.
CREATE TABLE providers (
    provider_id   INT PRIMARY KEY,
    provider_name VARCHAR(100),
    specialty     VARCHAR(50)
);

-- Admissions: the central event table. Every foreign key sits on
-- this "many" side and points at the "one" side (a patient has many
-- admissions, a ward has many admissions, etc.).
CREATE TABLE admissions (
    admission_id        INT PRIMARY KEY,
    patient_id          INT NOT NULL REFERENCES patients(patient_id),
    ward_number         INT NOT NULL REFERENCES wards(ward_number),
    provider_id         INT NOT NULL REFERENCES providers(provider_id),
    admission_date      DATE NOT NULL,
    discharge_date      DATE,
    reason_for_admission VARCHAR(100)
);
