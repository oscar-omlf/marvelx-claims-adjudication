from __future__ import annotations

"""FastAPI entrypoint for the MarvelX internal claims application.

The JSON API remains intentionally stable. This module adds human-facing pages
for internal operations, documentation, QA inspection, and claim submission,
while preserving the existing claim-processing behavior.
"""

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from claims_pipeline.api_models import ClaimResponse, ClaimSubmission
from claims_pipeline.explanation.generator import to_api_payload
from claims_pipeline.orchestrator import ClaimProcessor
from claims_pipeline.storage import ClaimStore

app = FastAPI(
    title="MarvelX Claims Adjudication",
    version="1.0.0",
    description="Internal claims processing and quality assurance platform.",
)
processor = ClaimProcessor()
store = ClaimStore()
templates = Jinja2Templates(directory=str(ROOT / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "app" / "static")), name="static")


LOGO_CANDIDATES = [
    "logo.svg",
    "logo.png",
    "logo.jpg",
    "logo.jpeg",
    "logo.webp",
]


def _logo_url() -> Optional[str]:
    """Return the configured brand asset if a manual logo file has been added.

    The app intentionally supports a drop-in logo workflow so branding can be
    finalized without changing application code. Place a company logo file in
    `app/static/` using one of the standard `logo.*` names.
    """
    static_dir = ROOT / "app" / "static"
    for filename in LOGO_CANDIDATES:
        if (static_dir / filename).exists():
            return f"/static/{filename}"
    return None


def _nav_context() -> Dict[str, Any]:
    """Return shared navigation metadata for human-facing templates."""
    qa_path = ROOT / "results" / "evaluation.json"
    predictions_path = ROOT / "results" / "predictions.jsonl"
    qa_available = qa_path.exists()
    predictions_available = predictions_path.exists() and predictions_path.stat().st_size > 0
    claim_count = len(store.list())
    return {
        "product_name": "MarvelX Claims Adjudication",
        "product_tagline": "Claims intake, deterministic adjudication, and QA visibility.",
        "logo_url": _logo_url(),
        "qa_available": qa_available,
        "predictions_available": predictions_available,
        "processed_claim_count": claim_count,
    }


def _render(request: Request, template_name: str, **context: Any) -> HTMLResponse:
    """Render a Jinja template with shared internal-product context."""
    payload = {**_nav_context(), **context, "request": request}
    return templates.TemplateResponse(template_name, payload)


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _first_claim_folder(path: Path) -> Path:
    """Return the directory that should be passed to the existing processor.

    ZIP uploads may contain either the claim files directly at the archive root
    or a single top-level claim folder. This helper keeps that packaging choice
    transparent to the submit UI.
    """
    directories = [item for item in path.iterdir() if item.is_dir() and item.name != "__MACOSX"]
    files = [item for item in path.iterdir() if item.is_file() and item.name != ".DS_Store"]
    if files:
        return path
    if len(directories) == 1:
        return directories[0]
    return path


@app.post("/claims", response_model=ClaimResponse)
def submit_claim(payload: ClaimSubmission):
    """Process a claim through the existing JSON API contract.

    Behavior is preserved: callers may either reference a claim directory on
    disk or submit inline description + text documents.
    """
    if payload.claim_path:
        claim_path = Path(payload.claim_path)
        if not claim_path.is_dir():
            raise HTTPException(status_code=400, detail="claim_path does not exist")
        assessment = processor.process_claim_dir(str(claim_path))
    else:
        if not payload.description:
            raise HTTPException(status_code=400, detail="description is required when claim_path is not provided")
        assessment = processor.process_inline_claim(
            claim_id=payload.claim_id or "inline_claim",
            description=payload.description,
            inline_documents=[d.model_dump() for d in payload.documents],
        )
    store.upsert(assessment)
    return ClaimResponse(**to_api_payload(assessment))


@app.get("/claims/{claim_id}", response_model=ClaimResponse)
def get_claim(claim_id: str):
    """Fetch a processed claim from the in-memory store."""
    item = store.get(claim_id)
    if item is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return ClaimResponse(**to_api_payload(item))


@app.get("/claims")
def list_claims():
    """List processed claims currently available in the in-memory store."""
    return [to_api_payload(item) for item in store.list()]


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Landing page for internal users."""
    qa_summary = _load_json(ROOT / "results" / "evaluation.json")
    return _render(request, "home.html", page_title="Operations Overview", qa_summary=qa_summary)


@app.get("/submit", response_class=HTMLResponse)
def submit_page(request: Request) -> HTMLResponse:
    """Render the internal claim submission form."""
    return _render(request, "submit.html", page_title="Claim Intake")


@app.post("/submit", response_class=HTMLResponse)
async def submit_page_post(
    request: Request,
    claim_id: str = Form(""),
    description: str = Form(""),
    metadata_json: str = Form("{}"),
    claim_package: UploadFile | None = File(default=None),
    supporting_files: list[UploadFile] = File(default=[]),
) -> HTMLResponse:
    """Handle multipart claim submission for the human-facing UI.

    This route is intentionally additive. It uses the same processing backend as
    the API but accepts uploaded files and optional claim ZIP packages so
    internal users can work directly from the browser without changing the
    stable JSON endpoint.
    """
    error: Optional[str] = None
    helper_note: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {}
    submitted_state = {"claim_id": claim_id, "description": description, "metadata_json": metadata_json}

    try:
        metadata = json.loads(metadata_json or "{}")
        if not isinstance(metadata, dict):
            raise ValueError("metadata_json must decode to an object")
    except Exception as exc:  # noqa: BLE001
        error = f"Invalid metadata JSON: {exc}"
        return _render(request, "submit.html", page_title="Claim Intake", error=error, submitted=submitted_state)

    if not description.strip() and not metadata.get("claim_path") and not claim_package:
        error = "A claim description is required unless metadata_json includes a valid claim_path or a claim package ZIP is uploaded."
        return _render(request, "submit.html", page_title="Claim Intake", error=error, submitted=submitted_state)

    if metadata.get("claim_path"):
        submission = ClaimSubmission(claim_id=claim_id or None, claim_path=str(metadata["claim_path"]))
        response = submit_claim(submission)
        result = response.model_dump()
    elif claim_package and claim_package.filename:
        with tempfile.TemporaryDirectory(prefix="marvelx-claim-zip-") as temp_dir:
            temp_path = Path(temp_dir)
            archive_path = temp_path / Path(claim_package.filename).name
            archive_path.write_bytes(await claim_package.read())
            try:
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(temp_path / "unzipped")
            except zipfile.BadZipFile:
                error = "The uploaded claim package is not a valid ZIP archive."
                return _render(request, "submit.html", page_title="Claim Intake", error=error, submitted=submitted_state)

            extracted_root = _first_claim_folder(temp_path / "unzipped")
            if description.strip() and not (extracted_root / "description.txt").exists():
                (extracted_root / "description.txt").write_text(description, encoding="utf-8")
            assessment = processor.process_claim_dir(str(extracted_root))
            if claim_id.strip():
                assessment.claim_id = claim_id.strip()
            store.upsert(assessment)
            result = to_api_payload(assessment)
            helper_note = "Claim package processed. All uploaded files in the ZIP were considered except evaluation files ignored by the pipeline."
    elif supporting_files:
        with tempfile.TemporaryDirectory(prefix="marvelx-claim-") as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "description.txt").write_text(description, encoding="utf-8")
            uploaded_names: list[str] = []
            for upload in supporting_files:
                if not upload.filename:
                    continue
                destination = temp_path / Path(upload.filename).name
                destination.write_bytes(await upload.read())
                uploaded_names.append(destination.name.lower())
            assessment = processor.process_claim_dir(str(temp_path))
            if claim_id.strip():
                assessment.claim_id = claim_id.strip()
            store.upsert(assessment)
            result = to_api_payload(assessment)

            has_structured_support = any(name.endswith((".md", ".txt")) for name in uploaded_names)
            if not has_structured_support:
                helper_note = (
                    "For benchmark-style claims, upload every original support file except answer.json. "
                    "That usually includes booking or itinerary markdown such as supporting1.md, "
                    "internal flight data.md, internal ticket data.md, or internal train data.md."
                )
            else:
                helper_note = (
                    "Uploaded files were processed together. Do not exclude the extra itinerary/support markdown files; "
                    "they are often required to prove booking, date, and route information."
                )
    else:
        documents = []
        for name, value in metadata.get("inline_documents", {}).items():
            documents.append({"filename": name, "content": str(value)})
        submission = ClaimSubmission(
            claim_id=claim_id or None,
            description=description,
            documents=documents,
        )
        response = submit_claim(submission)
        result = response.model_dump()

    return _render(
        request,
        "submit.html",
        page_title="Claim Intake",
        result=result,
        helper_note=helper_note,
        submitted=submitted_state,
    )


@app.get("/claims-ui", response_class=HTMLResponse)
def claims_page(request: Request) -> HTMLResponse:
    """Human-friendly list of processed claims stored in memory."""
    claims = [to_api_payload(item) for item in store.list()]
    return _render(request, "claims_list.html", page_title="Processed Claims", claims=claims)


@app.get("/claims-ui/{claim_id}", response_class=HTMLResponse)
def claim_detail_page(request: Request, claim_id: str) -> HTMLResponse:
    """Detailed internal inspection page for one processed claim."""
    item = store.get(claim_id)
    if item is None:
        raise HTTPException(status_code=404, detail="claim not found")
    return _render(
        request,
        "claim_detail.html",
        page_title=f"Claim {claim_id}",
        claim=item.to_dict(),
    )


@app.get("/qa", response_class=HTMLResponse)
def qa_page(request: Request) -> HTMLResponse:
    """Expose benchmark and QA artifacts already present in the repository."""
    evaluation = _load_json(ROOT / "results" / "evaluation.json")
    return _render(request, "qa.html", page_title="Benchmark & QA", evaluation=evaluation)


@app.get("/guide", response_class=HTMLResponse)
def guide_index(request: Request) -> HTMLResponse:
    """Entry page for internal engineering documentation."""
    return _render(request, "guide_index.html", page_title="Engineering Guide")


@app.get("/guide/architecture", response_class=HTMLResponse)
def guide_architecture(request: Request) -> HTMLResponse:
    return _render(request, "guide_architecture.html", page_title="App & Service Architecture")


@app.get("/guide/pipeline", response_class=HTMLResponse)
def guide_pipeline(request: Request) -> HTMLResponse:
    return _render(request, "guide_pipeline.html", page_title="Claim Processing Flow")


@app.get("/guide/modules", response_class=HTMLResponse)
def guide_modules(request: Request) -> HTMLResponse:
    return _render(request, "guide_modules.html", page_title="Module Map & Ownership")


@app.get("/guide/policy", response_class=HTMLResponse)
def guide_policy(request: Request) -> HTMLResponse:
    return _render(request, "guide_policy.html", page_title="Decision Policy & Verification Rules")


@app.get("/guide/results", response_class=HTMLResponse)
def guide_results(request: Request) -> HTMLResponse:
    evaluation = _load_json(ROOT / "results" / "evaluation.json")
    return _render(request, "guide_results.html", page_title="Benchmark Workflow & QA Artifacts", evaluation=evaluation)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.svg")
