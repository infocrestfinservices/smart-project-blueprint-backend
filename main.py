import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from config import settings

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
from routers.payment_router import router as payment_router
from routers.admin_router import router as admin_router
from routers.invoice_router import router as invoice_router
from routers.engine_test_router import router as engine_test_router  # dev only, see below

IS_PRODUCTION = settings.ENV.strip().lower() == "production"

# The automatic /docs, /redoc and /openapi.json are turned OFF and re-added below behind a
# guard. They list every endpoint and every field — a complete map of the attack surface —
# and they are only ever useful to staff.
app = FastAPI(
    title="AI Feasibility Study & Project Report Generator",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
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
app.include_router(payment_router)
app.include_router(admin_router)
app.include_router(invoice_router)
# The engine-test harness is a development tool. It is admin-only wherever it exists (see
# the router), and in production it does not exist at all — the strongest form of "not
# reachable" is "not mounted".
if not IS_PRODUCTION:
    app.include_router(engine_test_router)


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


# ── API docs ───────────────────────────────────────────────────────────────────
# Guarded with HTTP Basic rather than with the admin token, and the reason is mechanical:
# a browser navigating to /docs cannot attach an Authorization: Bearer header, and the
# Swagger page then fetches /openapi.json as a second request that cannot carry one either.
# Depends(get_admin_user) there would lock the team out along with everyone else. Basic auth
# is the one scheme a browser will prompt for and then replay on both requests.
#
# Outside production the docs stay open, because that is a developer's machine or a staging
# box. In production they exist only if DOCS_PASSWORD is set — no password, no docs. Failing
# closed is deliberate: forgetting to set a variable should hide the API reference, not
# publish it.
_basic = HTTPBasic(auto_error=False)


def _docs_guard(credentials: HTTPBasicCredentials = Depends(_basic)):
    if not IS_PRODUCTION:
        return True
    if not settings.DOCS_PASSWORD:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # compare_digest on both halves, so the comparison takes the same time whether the
    # username was wrong, the password was wrong, or both.
    ok_user = secrets.compare_digest((credentials.username if credentials else ""),
                                     settings.DOCS_USER)
    ok_pass = secrets.compare_digest((credentials.password if credentials else ""),
                                     settings.DOCS_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authorised",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


@app.get("/openapi.json", include_in_schema=False)
def openapi_schema(_=Depends(_docs_guard)):
    return app.openapi()


@app.get("/docs", include_in_schema=False)
def swagger_ui(_=Depends(_docs_guard)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API docs")
