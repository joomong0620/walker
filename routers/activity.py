from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from model.models import Healthcare
from database import get_db

router = APIRouter()  # 반드시 이 이름으로 정의

class ActivityTimeInput(BaseModel):
    user_id: str
    walker_id: str
    activity_time: int  # 활동 시간 (분 단위)

@router.post("/activity-time/")
async def add_activity_time(data: ActivityTimeInput, db: AsyncSession = Depends(get_db)):
    # 활동 시간 추가 로직
    result = await db.execute(
        select(Healthcare).where(
            (Healthcare.user_id == data.user_id) & 
            (Healthcare.walker_id == data.walker_id)
        )
    )
    healthcare = result.scalar()

    if not healthcare:
        raise HTTPException(status_code=404, detail="Healthcare record not found")

    healthcare.activity_time += data.activity_time
    await db.commit()
    await db.refresh(healthcare)

    return {"message": "Activity time updated successfully", "total_activity_time": healthcare.activity_time}
