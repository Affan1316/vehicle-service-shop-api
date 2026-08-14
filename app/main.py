import pathlib
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from urllib.parse import urlparse
import secure
from fastapi_pagination import add_pagination
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from sqlalchemy import text

from app.config import settings
from app.logging_config import setup_logging
from app.database import async_session, close_db_engine
from app.routers import (
    customers, visits, jobs, billing, resources, auth,
    inventory, diagnostics, reports, menu, files, audit
)
from app.exception_handlers import register_exception_handlers
from app.middleware import RequestLoggingMiddleware
from app.rate_limiter import limiter

# 1. INITIALIZE STRUCTURED LOGGING
setup_logging(log_level=settings.LOG_LEVEL)
logger = logging.getLogger("auto_shop.app")


# 2. APPLICATION LIFESPAN (STARTUP & SHUTDOWN)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup validation
    logger.info(
        "Starting application",
        extra={
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT,
            "email_enabled": settings.EMAIL_ENABLED,
            "upload_dir": settings.UPLOAD_DIR,
        }
    )

    # 1. Ensure upload directory exists
    try:
        upload_path = pathlib.Path(settings.UPLOAD_DIR)
        upload_path.mkdir(parents=True, exist_ok=True)
        logger.info("Upload directory verified at '%s'", upload_path.resolve())
    except Exception as e:
        logger.warning("Could not initialize upload directory '%s': %s", settings.UPLOAD_DIR, e)

    # 2. Validate database connectivity
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection test succeeded.")
    except Exception as e:
        logger.error("Database connection check failed on startup: %s", e)

    yield

    # Shutdown hooks
    logger.info("Shutting down application and releasing database connections...")
    try:
        await close_db_engine()
        logger.info("Database engine closed cleanly.")
    except Exception as e:
        logger.error("Error during database shutdown: %s", e)


# 3. FASTAPI INSTANTIATION
app = FastAPI(
    title=settings.APP_NAME,
    description="Backend API for vehicle service shop management: appointments, work orders, diagnostics, parts inventory, billing, PDF generation, email notifications, and file attachments.",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )

    from fastapi.routing import APIRoute

    def process_routes(routes, prefix=""):
        for route in routes:
            if isinstance(route, APIRoute):
                path = (prefix + route.path).replace("//", "/")
                for method in route.methods:
                    if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                        continue
                    operation = openapi_schema.get("paths", {}).get(path, {}).get(method.lower())
                    if not operation:
                        continue
                    required_roles = getattr(route.endpoint, "x-required-roles", None)
                    if required_roles:
                        operation["x-required-roles"] = list(required_roles)
            elif route.__class__.__name__ == "_IncludedRouter":
                context_prefix = getattr(route.include_context, "prefix", "")
                process_routes(route.original_router.routes, prefix + context_prefix)
            elif hasattr(route, "routes"):
                route_prefix = getattr(route, "path", "")
                process_routes(route.routes, prefix + route_prefix)

    process_routes(app.routes)
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# 4. RATE LIMITER CONFIGURATION
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 5. EXCEPTION HANDLERS
register_exception_handlers(app)

# 6. REQUEST LOGGING MIDDLEWARE
app.add_middleware(RequestLoggingMiddleware)

# 7. HTTP SECURITY HEADERS (USING SECURE LIBRARY)
referrer = secure.ReferrerPolicy().no_referrer()
xss = secure.CustomHeader(header="X-XSS-Protection", value="1; mode=block")
content = secure.XContentTypeOptions().nosniff()
frame = secure.XFrameOptions().deny()

if settings.ENVIRONMENT == "production":
    hsts = secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
    secure_headers = secure.Secure(referrer=referrer, custom=[xss], xcto=content, xfo=frame, hsts=hsts)
else:
    secure_headers = secure.Secure(referrer=referrer, custom=[xss], xcto=content, xfo=frame)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    secure_headers.set_headers(response)
    return response


# 8. CORS MIDDLEWARE
origins = []
for origin in settings.CORS_ORIGINS.split(","):
    clean_origin = origin.strip()
    if clean_origin:
        origins.append(clean_origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 9. TRUSTED HOST MIDDLEWARE
allowed_hosts = ["localhost", "127.0.0.1", "test"]
if settings.ENVIRONMENT == "production":
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.hostname:
            allowed_hosts.append(parsed.hostname)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# 10. INCLUDE API ROUTERS
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(customers.router, tags=["Customers & Vehicles"])
app.include_router(visits.router, tags=["Appointments & Visits"])
app.include_router(jobs.router, tags=["Work Orders & Line Items"])
app.include_router(billing.router, tags=["Billing & Financials"])
app.include_router(resources.router, tags=["Shop Resources"])
app.include_router(inventory.router, tags=["Inventory & Procurement"])
app.include_router(diagnostics.router, tags=["Diagnostic Inspections"])
app.include_router(reports.router, tags=["Reports & Analytics"])
app.include_router(menu.router, tags=["Canned Services Menu"])
app.include_router(files.router, tags=["File Attachments"])
app.include_router(audit.router, tags=["Audit Trail"])

# 11. FASTAPI PAGINATION EXTENSION
add_pagination(app)

# 12. PROMETHEUS METRICS INSTRUMENTATION
Instrumentator().instrument(app).expose(app)


@app.get("/")
async def root():
    """Welcome route providing documentation urls and app status."""
    return {
        "message": f"Welcome to the {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json"
    }


@app.get("/health", tags=["Infrastructure"])
async def health_check():
    """Liveness & readiness probe for load balancers and orchestrators."""
    from fastapi.responses import JSONResponse

    health = {
        "status": "healthy",
        "database": "connected",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT
    }
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        health = {
            "status": "unhealthy",
            "database": "disconnected",
            "detail": str(exc),
            "version": settings.APP_VERSION,
            "environment": settings.ENVIRONMENT
        }
        return JSONResponse(status_code=503, content=health)
    return health
