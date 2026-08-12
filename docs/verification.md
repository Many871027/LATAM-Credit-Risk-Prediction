# Verification Methodology & Traceability

This document defines how we verify functional correctness and ensure all business requirements are tracked and validated.

## 🔗 Requirement Traceability Matrix

Every feature developed in this repository must undergo Spec-Driven Development (SDD). To ensure correctness, every requirement `R<n>` (or `A<n>` for analytics) defined in `specs/<name>/requirements.md` must be linked to at least one automated test.

### Traceability Mapping Format
Before completing a feature, the implementer must document the traceability map in `progress/impl_<name>.md` using this layout:

```markdown
# Implementation Summary - CR-XXX

## Traceability Mapping
- **R1:** Verified by `tests.test_model.test_r1_gini_threshold`
- **R2:** Verified by `tests.test_api.test_r2_sub_100ms_latency`
...
```

## 🧪 Testing Suite Standards
- **Test Discovery:** All tests must reside in the `tests/` directory and be automatically discoverable by Python's `unittest` module.
- **Mocking External I/O:** Any database call (BigQuery) or external API connection (Vertex AI, Pub/Sub) must be mocked in unit tests.
- **Latency Testing:** Performance tests should mock typical concurrent payloads and verify that response latencies remain within bounds (e.g. < 100ms).

## 🟢 Pre-merge Verification Gate
No code may be merged, and no feature marked as `done`, unless `./init.sh` yields a 100% green status. The script runs:
1. Environment linting and syntax checking.
2. Spec directory existence validation.
3. Complete automated unit test discovery and execution.
