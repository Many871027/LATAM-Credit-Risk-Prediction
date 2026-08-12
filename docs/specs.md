# Spec-Driven Development (SDD) Protocol

This document defines the Spec-Driven Development (SDD) process mandated for all features inside this repository.

## 🔄 SDD Workflow

All feature additions follow this strict lifecycle:

```
pending → [spec_author] → spec_ready → ⏸ HUMAN APPROVAL → in_progress → [implementer → reviewer] → done
```

1. **Pending:** Feature is registered in `feature_list.json`.
2. **Spec Authoring:** The `spec_author` subagent drafts requirements, designs, and tasks.
3. **Spec Ready:** The specification is ready. Development is **paused** until the human provides approval.
4. **Implementation:** The `implementer` subagent builds code and tests.
5. **Review:** The `reviewer` subagent verifies coverage and standards.
6. **Done:** The feature is complete.

---

## 🔤 The EARS Syntax (Easy Approach to Requirements Syntax)

To ensure requirements are unambiguous, they must be formatted using one of the following patterns:

*   **Ubiquitous (General Requirements):**
    *   *Pattern:* The `<system name>` shall `<system response>`.
    *   *Example:* `R1: The API shall return HTTP 200 for health checks.`
*   **Event-Driven:**
    *   *Pattern:* WHEN `<trigger>`, the `<system name>` shall `<system response>`.
    *   *Example:* `R2: WHEN a credit scoring request is received, the system shall calculate the risk class.`
*   **Unwanted Behavior:**
    *   *Pattern:* IF `<undesired condition>`, the `<system name>` shall `<system response>`.
    *   *Example:* `R3: IF the input data is missing required fields, the system shall return HTTP 400.`
*   **State-Driven:**
    *   *Pattern:* WHILE `<in state>`, the `<system name>` shall `<system response>`.
    *   *Example:* `R4: WHILE the database is offline, the API shall fall back to cohort-level statistics.`

---

## 📂 The Three Core Files

For every feature, the `spec_author` creates these files in `specs/<feature_name>/`:

1.  **`requirements.md`**: Business requirements, inputs/outputs, KPIs, and EARS assertions.
2.  **`design.md`**: Tech stack, models, schemas, class architecture, and integration mapping.
3.  **`tasks.md`**: Step-by-step checklist of execution tasks for the implementer.
