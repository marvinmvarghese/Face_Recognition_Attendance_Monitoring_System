from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from .database import engine
from .migrations import ensure_attendance_schema
from .models import Base
from .routes.attendance import router as attendance_router
from .routes.auth import router as auth_router
from .routes.register import router as register_router

app = FastAPI(
    title="Face Recognition Attendance API",
    version="1.0.0",
    description="Production-oriented attendance backend with JWT auth and face recognition.",
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_attendance_schema(engine)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/web/")


app.include_router(auth_router)
app.include_router(register_router)
app.include_router(attendance_router)
app.mount("/web", StaticFiles(directory="web", html=True), name="web")
