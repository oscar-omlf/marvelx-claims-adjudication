# Architecture Summary

## Top-level components

- `app/main.py`: FastAPI entrypoint and internal UI routes
- `src/claims_pipeline/`: deterministic claim-processing pipeline
- `templates/`: internal product views
- `app/static/`: styling and static assets
- `scripts/`: benchmark processing and evaluation
- `results/`: QA artifacts

## Layer boundaries

### Application shell
The application shell owns routing, HTML rendering, and human-facing workflows.

### Pipeline core
The pipeline owns extraction, OCR, normalization, parsing, verification, and decision routing.

### QA artifacts
QA scripts and result files are kept separate from live route behavior so batch evaluation remains reproducible.
