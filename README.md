# MarvelX Claims Adjudication

An internal tool for processing travel-related insurance claims from a description and supporting evidence.

It provides:
- a FastAPI API,
- a browser UI for submitting and inspecting claims,
- deterministic claim adjudication,
- benchmark processing and evaluation scripts.

## What the system does

The system takes a claim description plus supporting files, extracts the relevant facts, checks them against the policy, and returns one of three decisions:

- `APPROVE`
- `DENY`
- `UNCERTAIN`

The pipeline is document-grounded. Supporting evidence matters more than the claimant narrative, and missing or contradictory proof can change the outcome even when the claimed reason would otherwise be covered.

## Main components

The project has three main parts:

### 1. API and internal UI
The FastAPI app exposes the JSON endpoints and also serves the internal pages used to submit claims, browse processed claims, and view system documentation.

### 2. Claim-processing pipeline
The pipeline handles:
- file loading,
- OCR for image-based evidence,
- multilingual normalization,
- parsing of booking/support files,
- document verification,
- policy-based decision routing.

### 3. Benchmark and evaluation tooling
The scripts in `scripts/` process the benchmark dataset and evaluate predictions separately from inference.

## Repository structure

```text
app/
  main.py
  static/
docs/
results/
scripts/
src/claims_pipeline/
templates/
tests/
policy.md
README.md
requirements.txt
````

## Requirements

* Python 3.9+
* Tesseract OCR installed and available on `PATH`

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the app

```bash
uvicorn app.main:app --reload
```

The app will start at:

```text
http://127.0.0.1:8000/
```

## Web interface

The app includes a small internal UI on top of the API.

Main routes:

* `/` - landing page
* `/submit` - submit a new claim in the browser
* `/claims-ui` - list processed claims
* `/claims-ui/{claim_id}` - inspect one processed claim
* `/qa` - benchmark / QA summary
* `/guide` - documentation home

Guide pages:

* `/guide/architecture`
* `/guide/pipeline`
* `/guide/modules`
* `/guide/policy`
* `/guide/results`

API reference:

* `/docs` - Swagger UI
* `/redoc` - ReDoc

## Submitting a claim

The easiest way to use the system is through `/submit`.

Typical workflow:

1. Paste the claim description.
2. Upload the supporting files.
3. Submit the claim.
4. Review the returned decision and explanation.

Alternatively, instead include the full claim evidence package in a ZIP file.

## API endpoints

### `POST /claims`

Process a claim.

### `GET /claims/{claim_id}`

Return one processed claim.

### `GET /claims`

List processed claims.

For the exact request and response schema, use `/docs`.

## Benchmark processing

### Run inference on the benchmark

```bash
python scripts/process_benchmark.py \
  --dataset-dir /path/to/dataset \
  --output-dir results
```

This writes prediction artifacts without reading `answer.json` during inference.

### Evaluate predictions

```bash
python scripts/evaluate_benchmark.py \
  --dataset-dir /path/to/dataset \
  --predictions results/predictions.jsonl \
  --output-dir results
```

Evaluation is separate from inference. `answer.json` is only used here.

## Current benchmark artifacts

Generated artifacts are stored in `results/`.

Current reference metrics:

* Strict accuracy: **96%**
* Relaxed accuracy: **100%**

Main files:

* `results/predictions.jsonl`
* `results/evaluation.json`
* `results/evaluation.md`

## How the decision pipeline works

At a high level, the pipeline does the following:

1. Load the claim description and supporting files.
2. Read text and markdown files directly.
3. Run OCR on image-based evidence.
4. Normalize multilingual content into a consistent matching layer.
5. Parse booking and support records.
6. Verify the supporting documents.
7. Route the case through deterministic policy logic.
8. Return a decision and short explanation.

The decision logic is explicit rather than model-driven. In general:

* official evidence outranks the narrative,
* missing required proof usually leads to `DENY`,
* contradictory official evidence usually leads to `DENY`,
* `UNCERTAIN` is used only for plausible but unresolved cases.

## Design choices

A few intentional choices in this repo:

* The adjudication core is deterministic and inspectable.
* OCR and normalization are used to support evidence extraction, not to replace policy logic.
* Benchmark inference and evaluation are kept separate.
* The UI is an internal convenience layer on top of the same backend pipeline.

## Assumptions and limitations

* OCR quality depends on the installed Tesseract version and source image quality.
* The claim store is in-memory / file-based application state, not a production database.
* The system is built around the supplied policy and benchmark, not as a generic insurance platform.
* The UI is intended for internal use and inspection, not as a full workflow product.
