-- SQL template to extract user behavioral features from Silver tables for DuckDB
-- Parameters:
--   1, 2, 3, 4: The observation date (as DATE)

SELECT 
  u.user_id,
  CAST(? AS DATE) AS observation_date,
  COALESCE(v.monthly_volume, 0.0) AS monthly_volume,
  COALESCE(r.session_regularity, 0) AS session_regularity
FROM silver.users u
LEFT JOIN (
  SELECT 
    user_id,
    COALESCE(SUM(amount), 0.0) AS monthly_volume
  FROM silver.loans
  WHERE disbursement_date >= CAST(? AS DATE) - INTERVAL 30 DAY
    AND disbursement_date <= CAST(? AS DATE)
  GROUP BY user_id
) v ON u.user_id = v.user_id
LEFT JOIN (
  SELECT 
    user_id,
    COUNT(DISTINCT CAST(session_timestamp AS DATE)) AS session_regularity
  FROM silver.user_sessions
  WHERE CAST(session_timestamp AS DATE) >= CAST(? AS DATE) - INTERVAL 30 DAY
    AND CAST(session_timestamp AS DATE) <= CAST(? AS DATE)
  GROUP BY user_id
) r ON u.user_id = r.user_id;
