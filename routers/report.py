from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from model.models import HeartRate, Activity
from datetime import datetime, timedelta

router = APIRouter()

# 주간 심박수 평균 조회 API
@router.get("/report/weekly-heartrate")
async def get_weekly_heartrate(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(HeartRate).where(HeartRate.user_id == user_id)
    )
    records = result.scalars().all()

    # 모든 요일 리스트 고정
    DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    summary = {day: [] for day in DAYS}

    for record in records:
        day_name = record.recorded_at.strftime("%a")  # 'Mon', 'Tue', ...
        if day_name in summary:
            summary[day_name].append(record.heartrate)

    # 없는 요일은 0 출력
    averaged = {day: int(sum(values) / len(values)) if values else 0 for day, values in summary.items()}

    return {"weekly_averages": averaged}


# 주간 활동 시간 평균 조회 API
@router.get("/report/weekly-activity")
async def get_weekly_activity(user_id: str, db: AsyncSession = Depends(get_db)):
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(Activity).where(
            Activity.user_id == user_id,
            Activity.start_time >= seven_days_ago
        )
    )
    records = result.scalars().all()

    # 요일별 집계
    summary = {}
    for record in records:
        day_name = record.start_time.strftime("%a")
        summary.setdefault(day_name, []).append(record.duration or 0)

    # 요일별 누적 시간 계산 (분 → 시간/분 포맷 변환)
    averaged = {day: f"{sum(values)//60}h {sum(values)%60}m" for day, values in summary.items()}

    return {"weekly_averages": averaged}
