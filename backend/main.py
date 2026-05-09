from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.database import engine, Base
from routers import jobs, users, credits

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas al iniciar
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="VoxLatam API",
    description="Servicio de transcripción, traducción y doblaje con IA",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router,    prefix="/jobs",    tags=["jobs"])
app.include_router(users.router,   prefix="/users",   tags=["users"])
app.include_router(credits.router, prefix="/credits", tags=["credits"])

@app.get("/health")
async def health():
    return {"status": "ok", "service": "voxlatam-api"}
