from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from model.models import Activity
from database import get_db
from datetime import datetime
from datetime import datetime, timedelta, timezone
router = APIRouter()

KST = timezone(timedelta(hours=9))

class ActivityAction(BaseModel):
    user_id: str
    walker_id: str

@router.post("/activity/start")
async def start_activity(data: ActivityAction, db: AsyncSession = Depends(get_db)):
    # 기존 미종료 활동이 있는지 확인
    result = await db.execute(
        select(Activity).where(
            (Activity.user_id == data.user_id) &
            (Activity.walker_id == data.walker_id) &
            (Activity.end_time == None)
        )
    )
    existing_activity = result.scalar()
    if existing_activity:
        raise HTTPException(status_code=400, detail="이미 시작된 활동이 있습니다.")

    new_activity = Activity(
        user_id=data.user_id,
        walker_id=data.walker_id,
        start_time=datetime.utcnow()
    )
    db.add(new_activity)
    await db.commit()
    await db.refresh(new_activity)

    # ✅ KST 변환 및 포맷
    KST = timezone(timedelta(hours=9))
    start_kst = new_activity.start_time.replace(tzinfo=timezone.utc).astimezone(KST)
    start_formatted = start_kst.strftime('%Y-%m-%d %H:%M:%S')

    return {"message": "활동이 시작되었습니다", "start_time": start_formatted}
# ✅ 활동 종료
@router.post("/activity/stop")
async def stop_activity(data: ActivityAction, db: AsyncSession = Depends(get_db)):
    # 가장 최근 미완료 활동 찾기
    result = await db.execute(
        select(Activity).where(
            (Activity.user_id == data.user_id) &
            (Activity.walker_id == data.walker_id) &
            (Activity.end_time == None)
        ).order_by(Activity.start_time.desc())
    )
    activity = result.scalar()

    if not activity:
        raise HTTPException(status_code=404, detail="종료할 활동이 없습니다.")

    end_time = datetime.utcnow()
    duration = int((end_time - activity.start_time).total_seconds() / 60)

    activity.end_time = end_time
    activity.duration = duration

    await db.commit()
    await db.refresh(activity)

    # ✅ KST 변환
    KST = timezone(timedelta(hours=9))
    start_kst = activity.start_time.replace(tzinfo=timezone.utc).astimezone(KST)
    end_kst = activity.end_time.replace(tzinfo=timezone.utc).astimezone(KST)

    # ✅ 원하는 형식으로 포맷
    start_formatted = start_kst.strftime('%Y-%m-%d %H:%M:%S')
    end_formatted = end_kst.strftime('%Y-%m-%d %H:%M:%S')

    return {
        "message": "활동이 종료되었습니다",
        "duration_min": duration,
        "start_time": start_formatted,
        "end_time": end_formatted
    }

