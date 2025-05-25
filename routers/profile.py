from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from model.models import User, Guardian

router = APIRouter()

@router.get("/profile/{id}")
async def get_profile(id: str, db: AsyncSession = Depends(get_db)):
    # 사용자 조회 시도
    result = await db.execute(select(User).where(User.user_id == id))
    user = result.scalar_one_or_none()
    if user:
        return {
            "id": user.user_id,
            "name": user.name,
            "contact": user.contact,
            "birth": user.birth,
            "user_type": "user"
        }

    # 보호자 조회 시도
    result = await db.execute(select(Guardian).where(Guardian.guardian_id == id))
    guardian = result.scalar_one_or_none()
    if guardian:
        return {
            "id": guardian.guardian_id,
            "name": guardian.name,
            "contact": guardian.contact,
            "birth": guardian.birth,
            "user_type": "guardian"
        }

    # 둘 다 없으면 404
    raise HTTPException(status_code=404, detail="User or Guardian not found")
