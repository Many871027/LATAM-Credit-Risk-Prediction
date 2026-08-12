# Checkpoints for Correct Final State

To ensure the SQL assessment is fully complete and correct, the following checkpoints must be met:

## Pre-requisites (EDA & Loading)
- [x] Run exploratory data analysis on the raw CSVs using `first_eda.py`.
- [x] Implement standard ISO-8601 formatting for date fields in `load_to_bigquery.py` and successfully ingest the data into BigQuery.

## Data Audit & Quality
- [x] Identify PK duplication rate (~7.95%) in `shipments_new`.
- [x] Identify data type parsing issues (slashes in date formats causing silent null conversion).
- [x] Identify event hour corruption (event_hour_utc truncating evening timestamps to 0).
- [x] Formulate a single unified data audit SQL query.

## Productivity & Metrics
- [x] Calculate stops efficiency and capacity utilization by country.
- [x] Identify underperforming routes with stops efficiency < 60%.
- [x] Exclude duplicate shipment counts dynamically in BigQuery metrics.

## Effectiveness
- [x] Calculate shipment success rate by country and partner.
- [x] Detect and explain the synthetic homogeneity of the dataset (success rate ~80.8% across all countries).

## OTH (On-Time Handling)
- [x] Calculate OTH by hour of fin and by duration.
- [x] Filter out routes with chronological violations (end time < start time).

## Timezone Investigation
- [x] Show that late-night deliveries in Colombia/Brazil are a UTC-0 timezone illusion.
- [x] Convert UTC-0 to local time using center timezone offset.

## Partner Consistency
- [x] Identify stale routes in `IN_PROGRESS` state.
- [x] Audit timezone/GPS synchronization issues and multi-regional routes.
- [x] Provide clear recommendations on whether to include PT-014 in metrics.

## Dashboard & Narrative
- [x] Create Looker Studio / Tableau dashboard mockup.
- [x] Formulate a 2-3 page narrative document structured as Problem -> Evidence -> Action.
