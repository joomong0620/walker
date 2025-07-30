from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import date
from model.models import ActivityDuration
from database import get_db

router = APIRouter()

# 📌 하루 누적 활동 시간 조회 API
@router.get("/activity/all_times")
async def get_all_activity_times(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ActivityDuration)
        .where(ActivityDuration.user_id == user_id)
        .where(ActivityDuration.walker_id == walker_id)
        .order_by(ActivityDuration.date.asc())
    )
    entries = result.scalars().all()

    return [
        {
            "user_id": e.user_id,
            "walker_id": e.walker_id,
            "date": str(e.date),
            "total_seconds": e.total_seconds
        }
        for e in entries
    ]
