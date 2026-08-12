-- SQL template to build default target (DPD30) from Silver tables for DuckDB
-- Parameters:
--   1, 2, 3: The observation date (as DATE)

SELECT 
  u.user_id,
  CAST(? AS DATE) AS observation_date,
  COALESCE(d.target_default_30d, 0) AS target_default_30d
FROM silver.users u
LEFT JOIN (
  SELECT 
    l.user_id,
    MAX(CASE 
      WHEN p.payment_date IS NOT NULL THEN CASE WHEN date_diff('day', p.due_date, p.payment_date) > 30 THEN 1 ELSE 0 END
      WHEN p.payment_date IS NULL AND CURRENT_DATE > p.due_date THEN CASE WHEN date_diff('day', p.due_date, CURRENT_DATE) > 30 THEN 1 ELSE 0 END
      ELSE 0
    END) AS target_default_30d
  FROM silver.loan_payments p
  JOIN silver.loans l ON p.loan_id = l.loan_id
  WHERE p.due_date > CAST(? AS DATE)
    AND p.due_date <= CAST(? AS DATE) + INTERVAL 12 MONTH
  GROUP BY l.user_id
) d ON u.user_id = d.user_id;
