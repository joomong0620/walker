from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from database import get_db
from model.models import AccelerometerData
from pydantic import BaseModel
import math

router = APIRouter()

# 요청 모델 정의
class AccelRequest(BaseModel):
    user_id: str
    walker_id: str
    ax: float
    ay: float
    az: float

# 단일 사용자 기준 상태 (멀티 사용자 지원은 추후 개선 가능)
is_walking = False
start_time = None
last_movement_time = None

# 임계값 설정
ACCEL_THRESHOLD = 1.5
STOP_TIMEOUT = 5  # 초

@router.post("/accelerometer")
async def handle_acceleration(
    data: AccelRequest,
    db: AsyncSession = Depends(get_db)
):
    global is_walking, start_time, last_movement_time

    # 벡터 크기 계산
    accel_value = math.sqrt(data.ax ** 2 + data.ay ** 2 + data.az ** 2)
    now = datetime.now()

    # DB 저장
    accel_entry = AccelerometerData(
        user_id=data.user_id,
        walker_id=data.walker_id,
        accel_value=accel_value,
        is_moving=int(accel_value > ACCEL_THRESHOLD),
        timestamp=now
    )
    db.add(accel_entry)
    await db.commit()

    # 보행 감지 로직
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

    return {
        "status": "saved",
        "accel_value": round(accel_value, 3),
        "is_walking": is_walking
    }
