from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from models.models import User

router = APIRouter()

@router.post("/add")
async def add_credits(telegram_id: str, amount_usd: float, db: AsyncSession = Depends(get_db)):
    """Agregar créditos a un usuario (llamado por el sistema de pago)."""
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id, credits_usd=amount_usd)
        db.add(user)
    else:
        user.credits_usd += amount_usd
    await db.commit()
    return {"telegram_id": telegram_id, "credits_usd": user.credits_usd}

@router.get("/{telegram_id}")
async def get_credits(telegram_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"credits_usd": 0.0}
    return {"credits_usd": user.credits_usd}
