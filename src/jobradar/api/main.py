from fastapi import FastAPI

from jobradar.api.routers import health

app = FastAPI(title="Job Radar")

# Every router is mounted under /api here, so routers only declare their own paths.
app.include_router(health.router, prefix="/api")
