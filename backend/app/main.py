import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api import identify, individuals
from app.core.config import BASE_DIR
from app.core.database import Base, SessionLocal, engine as db_engine
from app.core.retrain import retrain_from_db

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Registered Individual Identification System",
    description="Register individuals with face samples and identify them in real time via camera.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

app.include_router(individuals.router)
app.include_router(identify.router)

STATIC_DIR = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=db_engine)
    db = SessionLocal()
    try:
        retrain_from_db(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/register")
def register_page():
    return FileResponse(str(STATIC_DIR / "register.html"))


@app.get("/identify")
def identify_page():
    return FileResponse(str(STATIC_DIR / "identify.html"))


@app.get("/manage")
def manage_page():
    return FileResponse(str(STATIC_DIR / "manage.html"))
