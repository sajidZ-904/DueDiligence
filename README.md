Due Diligence Demo

Minimal skeleton for the Questionnaire Agent demo. See `backend/README.md` and
`frontend/README.md` for planned modules and endpoints.

Required Documentation
- Architecture Design: system overview, component boundaries, data flow, storage. See `docs/ARCHITECTURE_DESIGN.md`.
- Functional Design: user flows, API behaviors, status transitions, edge cases. See `docs/FUNCTIONAL_DESIGN.md`.
- Testing & Evaluation: dataset testing plan, QA checklist, evaluation metrics. See `docs/TESTING_EVALUATION.md`.

Dataset Testing
- Sample PDFs live in `data/` and are intended for ingestion and QA smoke tests.
- Use `data/ILPA_Due_Diligence_Questionnaire_v1.2.pdf` as the questionnaire input
  and the other PDFs as reference documents for answering.
- In your implementation, index the reference PDFs, create a project scoped to
  ALL_DOCS, and generate answers to validate citations/confidence outputs.
- Add a new document after indexing to confirm the ALL_DOCS project transitions
  to OUTDATED as described in the spec.
