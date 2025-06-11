from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from model.models import HeartRate  # 정확한 경로로 수정됨
from database import get_db

router = APIRouter()

# Pydantic 모델
class HeartRateCreate(BaseModel):
    user_id: str
    heartrate: int

# 심박수 기록 API
@router.post("/heartrate/")
async def create_heartrate(data: HeartRateCreate, db: AsyncSession = Depends(get_db)):
    new_entry = HeartRate(user_id=data.user_id, heartrate=data.heartrate)
    db.add(new_entry)
    try:
        await db.commit()
        await db.refresh(new_entry)
        return {"message": "Heart rate recorded successfully", "data": new_entry}
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database Commit Error")

# 심박수 조회 API
@router.get("/heartrate/{user_id}")
async def get_heartrate(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HeartRate).where(HeartRate.user_id == user_id).order_by(HeartRate.recorded_at.desc())
    )
    heartrate_records = result.scalars().all()
    if not heartrate_records:
        raise HTTPException(status_code=404, detail="No heart rate records found for this user")
    return heartrate_records
