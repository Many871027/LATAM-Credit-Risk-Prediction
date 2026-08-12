-- SQL template for idempotent merging of target constructions into gold.target_construction

INSERT OR REPLACE INTO gold.target_construction (
  user_id,
  observation_date,
  monthly_volume,
  session_regularity,
  target_default_30d
)
SELECT 
  user_id,
  CAST(observation_date AS DATE) AS observation_date,
  CAST(monthly_volume AS DOUBLE) AS monthly_volume,
  CAST(session_regularity AS INTEGER) AS session_regularity,
  CAST(target_default_30d AS INTEGER) AS target_default_30d
FROM staged_target_construction;
