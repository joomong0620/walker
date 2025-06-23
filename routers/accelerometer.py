from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from database import get_db
from model.models import AccelerometerData
from pydantic import BaseModel
import math

router = APIRouter()

# --------------------
# 요청 모델
# --------------------
class AccelRequest(BaseModel):
    user_id: str
    walker_id: str
    ax: float
    ay: float
    az: float

# --------------------
# POST: 센서 → 서버로 데이터 전송
# --------------------
@router.post("/accelerometer/")
async def receive_from_hardware(
    data: AccelRequest,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()
    accel_value = math.sqrt(data.ax ** 2 + data.ay ** 2 + data.az ** 2)

    # 최근 10초간 데이터 조회
    ten_seconds_ago = now - timedelta(seconds=10)
    result = await db.execute(
        select(AccelerometerData)
        .where(AccelerometerData.user_id == data.user_id)
        .where(AccelerometerData.walker_id == data.walker_id)
        .where(AccelerometerData.timestamp >= ten_seconds_ago)
        .order_by(desc(AccelerometerData.timestamp))
    )
    recent_entries = result.scalars().all()

    # 기본값
    is_moving = 0

    # 1️⃣ 현재 accel_value가 1.1 이상이면 → 10초 동안 유지
    if accel_value >= 1.1:
        is_moving = 1
    else:
        # 2️⃣ 최근 10초 이내에 is_moving = 1 이라도 하나라도 있으면 유지
        recent_has_moving = any(e.is_moving == 1 for e in recent_entries)
        if recent_has_moving:
            is_moving = 1

        # 3️⃣ 단, 최근 5개 이상이 0이면 멈춘 것으로 판단
        zero_count = sum(1 for e in recent_entries if e.is_moving == 0)
        if zero_count >= 5:
            is_moving = 0

    # 저장
    entry = AccelerometerData(
        user_id=data.user_id,
        walker_id=data.walker_id,
        accel_value=accel_value,
        is_moving=is_moving,
        timestamp=now
    )
    db.add(entry)
    await db.commit()

    print(f"DEBUG - accel_value: {accel_value:.3f}, is_moving: {is_moving}, zero_count: {zero_count if recent_entries else 0}")

    return {
        "message": "✅ 센서 데이터 저장 완료",
        "accel_value": round(accel_value, 3),
        "is_moving": is_moving,
        "timestamp": now.isoformat()
    }

# --------------------
# GET: 최신 데이터 요청
# --------------------
@router.get("/accelerometer/latest")
async def get_latest_data(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AccelerometerData)
        .where(AccelerometerData.user_id == user_id)
        .where(AccelerometerData.walker_id == walker_id)
        .order_by(desc(AccelerometerData.timestamp))
        .limit(1)
    )
    latest = result.scalar_one_or_none()

    if not latest:
        return {"message": "📭 데이터 없음"}

    return {
        "user_id": latest.user_id,
        "walker_id": latest.walker_id,
        "accel_value": round(latest.accel_value, 3),
        "is_moving": latest.is_moving,
        "timestamp": latest.timestamp.isoformat()
    }
