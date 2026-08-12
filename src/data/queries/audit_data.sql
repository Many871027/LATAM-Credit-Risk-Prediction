-- Data Quality Audit Query for DuckDB Medallion
-- Calculates counts of duplicates, nulls, and format conversion anomalies on bronze tables

SELECT
  -- 1. Users anomalies
  (SELECT COUNT(*) FROM bronze.users WHERE user_id IS NULL) AS users_null_pk,
  
  (SELECT COALESCE(SUM(dup_count - 1), 0) FROM (
     SELECT user_id, COUNT(*) as dup_count 
     FROM bronze.users 
     WHERE user_id IS NOT NULL 
     GROUP BY user_id 
     HAVING COUNT(*) > 1
  )) AS users_duplicate_pk,
  
  (SELECT COUNT(*) FROM bronze.users 
   WHERE user_id IS NOT NULL AND (
     TRY_CAST(replace(created_at, '/', '-') AS TIMESTAMP) IS NULL OR
     TRY_CAST(replace(updated_at, '/', '-') AS TIMESTAMP) IS NULL OR
     TRY_CAST(replace(ingestion_timestamp, '/', '-') AS TIMESTAMP) IS NULL
   )
  ) AS users_invalid_timestamps,

  -- 2. Sessions anomalies
  (SELECT COUNT(*) FROM bronze.user_sessions WHERE session_id IS NULL OR user_id IS NULL) AS sessions_null_pk,
  
  (SELECT COUNT(*) FROM bronze.user_sessions 
   WHERE session_id IS NOT NULL AND TRY_CAST(replace(session_timestamp, '/', '-') AS TIMESTAMP) IS NULL
  ) AS sessions_invalid_timestamp,

  -- 3. Loans anomalies
  (SELECT COUNT(*) FROM bronze.loans WHERE loan_id IS NULL OR user_id IS NULL) AS loans_null_pk,
  
  (SELECT COALESCE(SUM(dup_count - 1), 0) FROM (
     SELECT loan_id, COUNT(*) as dup_count 
     FROM bronze.loans 
     WHERE loan_id IS NOT NULL 
     GROUP BY loan_id 
     HAVING COUNT(*) > 1
  )) AS loans_duplicate_pk,
  
  (SELECT COUNT(*) FROM bronze.loans 
   WHERE loan_id IS NOT NULL AND (
     COALESCE(
       TRY_CAST(replace(disbursement_date, '/', '-') AS DATE),
       CAST(try_strptime(disbursement_date, '%d-%m-%Y') AS DATE)
     ) IS NULL
   )
  ) AS loans_invalid_disbursement_date,
  
  (SELECT COUNT(*) FROM bronze.loans 
   WHERE loan_id IS NOT NULL AND TRY_CAST(amount AS DOUBLE) IS NULL
  ) AS loans_invalid_amount,

  -- 4. Payments anomalies
  (SELECT COUNT(*) FROM bronze.loan_payments WHERE payment_id IS NULL OR loan_id IS NULL) AS payments_null_pk,
  
  (SELECT COALESCE(SUM(dup_count - 1), 0) FROM (
     SELECT payment_id, COUNT(*) as dup_count 
     FROM bronze.loan_payments 
     WHERE payment_id IS NOT NULL 
     GROUP BY payment_id 
     HAVING COUNT(*) > 1
  )) AS payments_duplicate_pk,
  
  (SELECT COUNT(*) FROM bronze.loan_payments 
   WHERE payment_id IS NOT NULL AND (
     COALESCE(
       TRY_CAST(replace(due_date, '/', '-') AS DATE),
       CAST(try_strptime(due_date, '%d-%m-%Y') AS DATE)
     ) IS NULL
   )
  ) AS payments_invalid_due_date,
  
  (SELECT COUNT(*) FROM bronze.loan_payments 
   WHERE payment_id IS NOT NULL AND payment_date IS NOT NULL AND (
     COALESCE(
       TRY_CAST(replace(payment_date, '/', '-') AS DATE),
       CAST(try_strptime(payment_date, '%d-%m-%Y') AS DATE)
     ) IS NULL
   )
  ) AS payments_invalid_payment_date,
  
  (SELECT COUNT(*) FROM bronze.loan_payments 
   WHERE payment_id IS NOT NULL AND (
     TRY_CAST(amount_due AS DOUBLE) IS NULL OR
     TRY_CAST(amount_paid AS DOUBLE) IS NULL
   )
  ) AS payments_invalid_amounts;
