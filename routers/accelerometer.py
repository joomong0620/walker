# routers/accelerometer.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from database import get_db
from model.models import AccelerometerData  # ← 모델 import
from pydantic import BaseModel
router = APIRouter()

# ✅ 요청 모델 정의
class AccelRequest(BaseModel):
    accel: float
    user_id: str
    walker_id: str


# 간단한 상태 저장
is_walking = False
start_time = None
last_movement_time = None

ACCEL_THRESHOLD = 1.5
STOP_TIMEOUT = 5


@router.post("/accelerometer")
async def handle_acceleration(
    data: dict,
    db: AsyncSession = Depends(get_db)
):
    global is_walking, start_time, last_movement_time

    accel_value = data.get("accel", 0)
    user_id = data.get("user_id")
    walker_id = data.get("walker_id")
    now = datetime.now()

    # DB에 가속도 기록 저장
    accel_entry = AccelerometerData(
        user_id=user_id,
        walker_id=walker_id,
        accel_value=accel_value,
        is_moving=int(accel_value > ACCEL_THRESHOLD),
        timestamp=now
    )
    db.add(accel_entry)
    await db.commit()

    # 자동 시작/종료 감지 로직
    if accel_value > ACCEL_THRESHOLD:
        if not is_walking:
            start_time = now
            is_walking = True
            print(f"[START] 보행 시작 시간: {start_time}")
        last_movement_time = now

    elif is_walking and last_movement_time:
        if (now - last_movement_time) > timedelta(seconds=STOP_TIMEOUT):
            end_time = now
            duration = (end_time - start_time).total_seconds()
            is_walking = False
            print(f"[STOP] 보행 종료 시간: {end_time}")
            print(f"[TOTAL] 총 보행 시간: {duration:.1f}초")

    return {"status": "saved", "is_walking": is_walking}
