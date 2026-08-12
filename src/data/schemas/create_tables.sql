-- DDL script for BigQuery tables

-- Create schemas/datasets if they do not exist
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS credit_risk;

-- 1. raw.users
CREATE TABLE IF NOT EXISTS raw.users (
  user_id STRING,
  created_at TIMESTAMP,
  country STRING,
  updated_at TIMESTAMP,
  ingestion_timestamp TIMESTAMP
);

-- 2. raw.user_sessions
CREATE TABLE IF NOT EXISTS raw.user_sessions (
  session_id STRING,
  user_id STRING,
  session_timestamp TIMESTAMP
);

-- 3. raw.loans
CREATE TABLE IF NOT EXISTS raw.loans (
  loan_id STRING,
  user_id STRING,
  disbursement_date DATE,
  amount NUMERIC,
  term_months INT64,
  updated_at TIMESTAMP,
  ingestion_timestamp TIMESTAMP
);

-- 4. raw.loan_payments
CREATE TABLE IF NOT EXISTS raw.loan_payments (
  payment_id STRING,
  loan_id STRING,
  due_date DATE,
  payment_date DATE,
  amount_due NUMERIC,
  amount_paid NUMERIC,
  updated_at TIMESTAMP,
  ingestion_timestamp TIMESTAMP
);

-- Target analytical table: credit_risk.target_construction
CREATE TABLE IF NOT EXISTS credit_risk.target_construction (
  user_id STRING NOT NULL,
  observation_date DATE NOT NULL,
  monthly_volume NUMERIC NOT NULL,
  session_regularity INT64 NOT NULL,
  target_default_30d INT64 NOT NULL
)
PARTITION BY observation_date
CLUSTER BY user_id;
