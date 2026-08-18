from fastapi import FastAPI  
from fastapi.middleware.cors import CORSMiddleware  # Middleware to enable Cross-Origin Resource Sharing (CORS)
from fastapi.openapi.utils import get_openapi
from app.config import settings  # Application configuration settings loaded from environment
from app.logging_config import setup_logging  # Function to configure structured JSON logging
from app.routers import (
    customers, visits, jobs, billing, resources, auth, inventory, diagnostics,
    communications, catalog, labor, accounting, reports, menu, files, audit
)  # Modular API router groups
from app.exception_handlers import register_exception_handlers  # Global database/app error handler registration
from app.middleware import RequestLoggingMiddleware  # Custom middleware to track request duration and correlation IDs

from app.rate_limiter import limiter  # Rate limiter instance using slowapi library
from slowapi.errors import RateLimitExceeded  # Exception raised when a user exceeds the request rate limit
from slowapi import _rate_limit_exceeded_handler  # Standard handler to convert RateLimitExceeded to an HTTP response
import secure  # Library to automatically apply HTTP security headers (X-Frame-Options, HSTS, etc.)
from fastapi_pagination import add_pagination  # Helper to register pagination mechanisms with the FastAPI app
from prometheus_fastapi_instrumentator import Instrumentator

# 1. INITIALIZE STRUCTURED LOGGING
# We run setup_logging immediately at startup so that all subsequent logs 
# (including FastAPI startup events) are formatted as structured JSON.
setup_logging(log_level=settings.LOG_LEVEL)

# 2. FASTAPI INSTANTIATION
app = FastAPI(
    title="Vehicle Service Shop API",
    description="Backend API for managing customer visits, quotes, work orders, resources, and billing.",
    version="0.1.0"
)

def custom_openapi():
    #  To avoid wasting CPU cycles, it saves the generated schema into the application 
    # instance's .openapi_schema attribute. If it is requested again, it returns the cached 
    # copy instantly instead of rebuilding it.and we are chacking for it here first 
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

# 3. RATE LIMITER CONFIGURATION
# Attach the slowapi Limiter instance to application state so that the route decorators 
# can check the request rate limits. We also register the rate limit exceeded exception handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 4. EXCEPTION HANDLERS
# Register global exception handlers to clean up operational and database exceptions 
# and return formatted JSON error messages to clients.
register_exception_handlers(app)

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import Response
from urllib.parse import urlparse

# 5. REQUEST LOGGING MIDDLEWARE
# Tracks execution time and correlation ID for every incoming HTTP request.
# Added as the outermost middleware so it wraps all others.
app.add_middleware(RequestLoggingMiddleware)

# 6. HTTP SECURITY HEADERS (USING SECURE LIBRARY)
# Define standard security policies to prevent security vulnerabilities like Clickjacking, 
# MIME Sniffing, and Cross-Site Scripting (XSS).
referrer = secure.ReferrerPolicy().no_referrer()
xss = secure.CustomHeader(header="X-XSS-Protection", value="1; mode=block")
content = secure.XContentTypeOptions().nosniff()
frame = secure.XFrameOptions().deny()

# Only enable Strict-Transport-Security (HSTS) in production (forces HTTPS connection)
if settings.ENVIRONMENT == "production":
    hsts = secure.StrictTransportSecurity().max_age(31536000).include_subdomains()
    secure_headers = secure.Secure(referrer=referrer, custom=[xss], xcto=content, xfo=frame, hsts=hsts)
else:
    secure_headers = secure.Secure(referrer=referrer, custom=[xss], xcto=content, xfo=frame)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Middleware wrapper that applies security headers to every response."""
    response = await call_next(request)
    secure_headers.set_headers(response)
    return response

# 7. CORS MIDDLEWARE
# Cross-Origin Resource Sharing (CORS) determines which frontend client domains 
# are allowed to make API calls to this backend.
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

# 8. TRUSTED HOST MIDDLEWARE
# Secures the application against HTTP Host Header attacks by checking 
# that request hosts match a list of trusted domain names.
allowed_hosts = ["localhost", "127.0.0.1", "test"]  # 'test' is used by httpx ASGITransport during testing
if settings.ENVIRONMENT == "production":
    for origin in origins:
        parsed = urlparse(origin)
        if parsed.hostname:
            allowed_hosts.append(parsed.hostname)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=allowed_hosts
)

# 9. INCLUDE API ROUTERS
# Mount the modular routers that handle different resource models of our application.
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(customers.router, tags=["Customers & Vehicles"])
app.include_router(visits.router, tags=["Appointments & Visits"])
app.include_router(jobs.router, tags=["Work Orders & Line Items"])
app.include_router(billing.router, tags=["Billing & Financials"])
app.include_router(resources.router, tags=["Shop Resources"])
app.include_router(inventory.router, tags=["Inventory & Procurement"])
app.include_router(diagnostics.router, tags=["Diagnostic Inspections"])
app.include_router(communications.router, tags=["Communications"])
app.include_router(catalog.router, tags=["Catalog"])
app.include_router(labor.router, tags=["Labor"])
app.include_router(accounting.router, tags=["Accounting & Sync"])
app.include_router(reports.router, tags=["Reports & Analytics"])
app.include_router(menu.router, tags=["Canned Services Menu"])
app.include_router(files.router, tags=["File Attachments"])
app.include_router(audit.router, tags=["Audit Trail"])


# 10. FASTAPI PAGINATION EXTENSION
# Initializes the fastapi-pagination framework to handle automatic pagination.
add_pagination(app)

# 11. PROMETHEUS METRICS INSTRUMENTATION
# Instrument the FastAPI app and expose a /metrics endpoint for Prometheus scraping.
Instrumentator().instrument(app).expose(app)

@app.get("/")
async def root():
    """Welcome route providing documentation urls."""
    return {
        "message": "Welcome to the Vehicle Service Shop API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

@app.get("/health", tags=["Infrastructure"])
async def health_check():
    """Liveness & readiness probe for load balancers and orchestrators."""
    from sqlalchemy import text
    from app.database import async_session
    from fastapi.responses import JSONResponse

    health = {"status": "healthy", "database": "connected"}
    try:
        # Run a simple query to confirm database is reachable
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        health = {
            "status": "unhealthy",
            "database": "disconnected",
            "detail": str(exc)
        }
        return JSONResponse(status_code=503, content=health)
    return health
