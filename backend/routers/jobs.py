from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
from celery import Celery
import uuid, shutil, os

from core.database import get_db
from core.config import settings
from models.models import Job, User, JobMode, JobStatus

router = APIRouter()

# Cliente Celery solo para enviar tareas
celery_app = Celery("voxlatam", broker=os.getenv("REDIS_URL", "redis://redis:6379/0"))
celery_app.conf.task_default_queue = "voxlatam"

@router.post("/")
async def create_job(
    file: UploadFile = File(...),
    mode: JobMode = Form(JobMode.transcription),
    lang_source: str = Form("auto"),
    lang_target: str = Form("es"),
    telegram_user_id: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Buscar o crear usuario
    user = None
    if telegram_user_id:
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            user = User(telegram_id=telegram_user_id, credits_usd=30.0)
            db.add(user)
            await db.flush()

    # Crear job
    job_id = str(uuid.uuid4())
    job_dir = Path(settings.storage_path) / job_id 
    job_dir.mkdir(parents=True, exist_ok=True)

    # Guardar archivo subido
    suffix = Path(file.filename).suffix if file.filename else ".ogg"
    input_path = job_dir / f"input{suffix}"
    with open(input_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    job = Job(
        id=job_id,
        user_id=user.id if user else None,
        mode=mode,
        lang_source=lang_source,
        lang_target=lang_target,
        status=JobStatus.queued
    )
    db.add(job)
    await db.commit()

    # Enviar tarea al worker via Redis
    celery_app.send_task(
        "tasks.process_job",
        args=[job_id, {
            "mode": str(mode.value),
            "lang_source": lang_source,
            "lang_target": lang_target,
            "input_path": str(input_path)
        }],
        queue="voxlatam"
    )

    return {"job_id": job_id, "status": "queued"}


@router.get("/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id":       str(job.id),
        "status":   job.status,
        "progress": job.progress,
        "mode":     job.mode,
        "cost_usd": job.cost_usd,
        "files": {
            "srt":       job.file_srt,
            "txt":       job.file_txt,
            "subtitled": job.file_subtitled,
            "dubbed":    job.file_dubbed,
        }
    }


@router.get("/user/{telegram_id}")
async def get_user_jobs(telegram_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return []
    jobs_result = await db.execute(
        select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(20)
    )
    return [{"id": str(j.id), "status": j.status, "mode": j.mode, "created_at": str(j.created_at)}
            for j in jobs_result.scalars()]
