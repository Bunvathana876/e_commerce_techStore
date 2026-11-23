from pathlib import Path
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.gzip import GZipMiddleware

from app.api.v1 import api_router, api_v1_router
from app.core.config import Settings, settings
from app.core.dependencies import require_roles
from app.core.rate_limit import RateLimitExceeded
from app.db.database import Base, engine, get_db
import app.models  # noqa: F401 (Import all models to register with Base metadata)
from app.models.user import User

ALLOWED_CORS_METHODS: list[str] = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
ALLOWED_CORS_HEADERS: list[str] = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Origin",
    "User-Agent",
    "X-Requested-With",
    "Idempotency-Key",
    "idempotency-key",
]

# In development, auto-init can create tables if requested.
# In production, automatic create_all is disabled to enforce Alembic migrations.
if settings.AUTO_INIT_DB:
    if not settings.is_production:
        Base.metadata.create_all(bind=engine)
    else:
        # Production environments must use verified Alembic migrations
        import logging
        logging.getLogger("uvicorn.error").info(
            "Notice: AUTO_INIT_DB create_all is bypassed in production. Schema is managed via Alembic."
        )

    # Seed initial notifications and accounts once on startup if empty
    try:
        with Session(bind=engine) as init_db:
            if not settings.is_production and settings.SEED_DEMO_DATA:
                from app.services.notification_service import NotificationService
                from app.db.seed_data import seed_database
                NotificationService.seed_sample_notifications_if_empty(init_db)
                seed_database()
    except Exception as e:
        print(f"Startup seed note: {e}")


def _render_developer_landing_page(version: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>E-Commerce Backend &amp; Services</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      background: #0f172a;
      color: #f8fafc;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }}
    .container {{
      width: 100%;
      max-width: 720px;
      background: rgba(30, 41, 59, 0.7);
      backdrop-filter: blur(16px);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 24px;
      padding: 40px;
      box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34d399;
      border-radius: 9999px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 20px;
    }}
    .pulse-dot {{
      width: 8px;
      height: 8px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 12px #10b981;
    }}
    h1 {{
      font-size: 32px;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: 8px;
      background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    p.subtitle {{
      color: #94a3b8;
      font-size: 15px;
      line-height: 1.6;
      margin-bottom: 32px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }}
    .card {{
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 20px;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 16px;
      text-decoration: none;
      color: inherit;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .card:hover {{
      transform: translateY(-2px);
      border-color: rgba(99, 102, 241, 0.4);
      background: rgba(30, 41, 59, 0.8);
      box-shadow: 0 10px 25px -5px rgba(99, 102, 241, 0.15);
    }}
    .card-icon {{
      font-size: 24px;
      margin-bottom: 12px;
    }}
    .card-title {{
      font-size: 16px;
      font-weight: 700;
      color: #f1f5f9;
      margin-bottom: 4px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .card-desc {{
      font-size: 13px;
      color: #64748b;
      line-height: 1.5;
    }}
    .tag {{
      font-size: 11px;
      padding: 2px 8px;
      background: rgba(99, 102, 241, 0.15);
      color: #818cf8;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
    }}
    .footer {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-top: 24px;
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      font-size: 13px;
      color: #64748b;
    }}
    .footer a {{
      color: #818cf8;
      text-decoration: none;
    }}
    .footer a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="badge">
      <span class="pulse-dot"></span>
      Backend API Online • v{version}
    </div>
    <h1>E-Commerce API &amp; Backend</h1>
    <p class="subtitle">
      The FastAPI server is running smoothly. Choose where you want to go:
    </p>

    <div class="grid">
      <a href="http://localhost:3000" class="card">
        <div>
          <div class="card-icon">🛍️</div>
          <div class="card-title">
            Customer Storefront
            <span class="tag">:3000</span>
          </div>
          <div class="card-desc">Customer shopping catalog, cart sync, Stripe &amp; COD checkout, and order tracking.</div>
        </div>
      </a>

      <a href="http://localhost:3001/admin" class="card">
        <div>
          <div class="card-icon">💻</div>
          <div class="card-title">
            Management Portal
            <span class="tag">:3001</span>
          </div>
          <div class="card-desc">Admin &amp; seller portal for products, orders, shipments, inventory, coupons, and settings.</div>
        </div>
      </a>

      <a href="http://localhost:3001/admin/pos" class="card">
        <div>
          <div class="card-icon">🛒</div>
          <div class="card-title">
            Point of Sale (POS)
            <span class="tag">:3001/pos</span>
          </div>
          <div class="card-desc">Retail cashier counter, barcode scan, cart management, cash change calculator, and thermal receipts.</div>
        </div>
      </a>

      <a href="/docs" class="card">
        <div>
          <div class="card-icon">📖</div>
          <div class="card-title">
            Interactive Swagger Docs
            <span class="tag">:8000/docs</span>
          </div>
          <div class="card-desc">Test and explore all REST endpoints, schemas, authentication, and responses.</div>
        </div>
      </a>

      <a href="http://localhost:5050" target="_blank" class="card">
        <div>
          <div class="card-icon">🐘</div>
          <div class="card-title">
            pgAdmin 4 Database
            <span class="tag">:5050</span>
          </div>
          <div class="card-desc">Inspect PostgreSQL 16 tables, run raw queries, and manage database records.</div>
        </div>
      </a>
    </div>

    <div class="footer">
      <span>Raw JSON: <a href="/?format=json">/?format=json</a></span>
      <span>API Health: <a href="/health">/health</a></span>
    </div>
  </div>
</body>
</html>"""


def create_app(custom_settings: Settings | None = None) -> CORSMiddleware:
    cfg = custom_settings or settings

    # In production, documentation and OpenAPI schemas are disabled by default
    docs_url = (
        "/docs"
        if (not cfg.is_production or cfg.ENABLE_DOCS_IN_PRODUCTION)
        else None
    )
    redoc_url = (
        "/redoc"
        if (not cfg.is_production or cfg.ENABLE_DOCS_IN_PRODUCTION)
        else None
    )
    openapi_url = (
        "/openapi.json"
        if (not cfg.is_production or cfg.ENABLE_DOCS_IN_PRODUCTION)
        else None
    )

    app_instance = FastAPI(
        title=cfg.PROJECT_NAME,
        description=cfg.PROJECT_DESCRIPTION,
        version=cfg.PROJECT_VERSION,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )

    # Standardized Rate Limit Exceeded exception handler (RFC 6585)
    @app_instance.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
        headers = {
            "Retry-After": str(exc.retry_after),
            "X-RateLimit-Limit": str(exc.limit),
            "X-RateLimit-Remaining": str(exc.remaining),
            "X-RateLimit-Reset": str(exc.reset_seconds),
        }
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "message": f"Too many requests. Please try again in {exc.retry_after} seconds.",
                "error_code": "RATE_LIMIT_EXCEEDED",
                "detail": exc.detail,
            },
            headers=headers,
        )

    # Wrap in GZipMiddleware to compress large JSON responses (>= 1KB)
    app_instance.add_middleware(GZipMiddleware, minimum_size=1000)

    # Standard security headers middleware
    @app_instance.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Mount static files to serve uploaded images
    uploads_dir = Path(cfg.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "products").mkdir(parents=True, exist_ok=True)
    app_instance.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

    # Include all API routes (both /api and /api/v1 for mobile & web clients)
    app_instance.include_router(api_router)
    app_instance.include_router(api_v1_router)

    @app_instance.get("/", response_class=HTMLResponse)
    def root(request: Request):
        if cfg.is_production:
            return JSONResponse({
                "message": "E-Commerce API is running",
                "status": "success",
                "version": cfg.PROJECT_VERSION,
            })

        format_param = request.query_params.get("format", "").lower()
        accept_header = request.headers.get("accept", "")

        if format_param == "json" or (
            "application/json" in accept_header and "text/html" not in accept_header
        ):
            return JSONResponse({
                "message": "E-Commerce API is running",
                "status": "success",
                "version": cfg.PROJECT_VERSION,
            })

        return HTMLResponse(content=_render_developer_landing_page(cfg.PROJECT_VERSION))

    @app_instance.get("/health")
    def health_check():
        return {
            "status": "healthy",
        }

    @app_instance.get("/readyz")
    def readiness_check(db: Session = Depends(get_db)):
        try:
            db.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "database": "connected",
            }
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database is unavailable",
            )

    # Development-only database diagnostic endpoint
    if not cfg.is_production:
        @app_instance.get("/db-test")
        def database_test(
            db: Session = Depends(get_db),
            current_user: User = Depends(require_roles("admin")),
        ):
            result = db.execute(text("SELECT 1"))
            value = result.scalar_one()

            dialect = db.bind.dialect.name if db.bind else "unknown"
            return {
                "database": dialect,
                "connection": "success",
                "test_value": value,
            }

    # Wrap ServerErrorMiddleware too, so trusted clients can read unhandled 500s.
    return CORSMiddleware(
        app=app_instance,
        allow_origins=cfg.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOWED_CORS_METHODS,
        allow_headers=ALLOWED_CORS_HEADERS,
        max_age=600,
    )


app = create_app()
