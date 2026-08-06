from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.industry_router import router as industry_router
from routers.country_router import router as country_router
from routers.purpose_router import router as purpose_router
from routers.ai_router import router as ai_router
from routers.project_router import router as project_router
from routers.analysis_router import router as analysis_router
from routers.auth_router import router as auth_router
from routers.generation_router import router as generation_router
from routers.templates_router import router as templates_router
from routers.bank_loan_router import router as bank_loan_router
from routers.engine_test_router import router as engine_test_router  # temporary: engine validation

app = FastAPI(
    title="AI Feasibility Study & Project Report Generator",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Cross-origin JS can only read "simple" response headers unless the server
    # explicitly exposes others. The file-download endpoints put the real
    # filename (and its .xlsx/.xlsm extension) in Content-Disposition; without
    # exposing it the frontend can't read it and falls back to a wrong
    # extension, so a valid .xlsm gets saved as .xlsx and Excel rejects it.
    expose_headers=["Content-Disposition"],
)

app.include_router(industry_router)
app.include_router(country_router)
app.include_router(purpose_router)
app.include_router(ai_router)
app.include_router(project_router)
app.include_router(analysis_router)
app.include_router(auth_router)
app.include_router(generation_router)
app.include_router(templates_router)
app.include_router(bank_loan_router)
app.include_router(engine_test_router)  # temporary: engine validation, remove before prod


@app.on_event("startup")
def _register_folder_templates():
    """Auto-register any template files dropped under templates/<category>/ so the
    platform is truly template-driven: add a file, restart, it's available — no code
    changes. Idempotent and non-fatal (a bad file is skipped, never blocks boot)."""
    import logging
    try:
        from services.template_upload_service import scan_templates_dir
        added = scan_templates_dir()
        ok = [a for a in added if a.get("template_id")]
        if added:
            logging.getLogger("templates").info(
                "startup: registered %d folder template(s); %d skipped/errored",
                len(ok), len(added) - len(ok))
    except Exception:
        logging.getLogger("templates").warning("startup template scan failed", exc_info=True)


@app.get("/")
def home():
    return {"message": "Backend is working"}

@app.get("/health")
def health():
    return {"status": "healthy"}