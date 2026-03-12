# MarvelX Claims Adjudication --- Internal Approach

This repository implements a deterministic, document-aware claims adjudication platform designed for internal use by engineering, QA, and operations teams.

## Product intent

The system supports three core internal workflows:

1. **Claim intake** for structured or ad hoc internal testing
2. **Decision inspection** for reviewing outputs, extracted facts, and warnings
3. **Quality assurance** for benchmark processing and evaluation

## Architectural stance

The application is intentionally split into two layers:

- a thin FastAPI application shell for API and internal UI routes
- a deterministic claims-processing pipeline under `src/claims_pipeline`

This separation keeps the adjudication logic inspectable and stable while allowing the internal product surface to evolve independently.

## Processing principles

- Official evidence outranks claimant narrative.
- Missing required proof generally routes to `DENY`.
- Contradictory authoritative evidence generally routes to `DENY`.
- `UNCERTAIN` is reserved for plausible-but-unresolved cases.
- OCR and multilingual normalization support the decision pipeline but do not replace deterministic policy routing.

## Operational surfaces

- `/`: internal landing page
- `/submit`: human-friendly claim intake UI
- `/claims-ui`: processed claims inspection
- `/qa`: benchmark and evaluation summary
- `/guide/*`: engineering and operations guide pages
- `/docs` and `/redoc`: API documentation
