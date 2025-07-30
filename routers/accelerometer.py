from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from database import get_db
from model.models import AccelerometerData
from model.models import ActivityDuration  
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
    pitch: float
    slope: str

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

    # 최근 5초간 데이터 조회 (기간 늘림)
    five_seconds_ago = now - timedelta(seconds=5)
    result = await db.execute(
        select(AccelerometerData)
        .where(AccelerometerData.user_id == data.user_id)
        .where(AccelerometerData.walker_id == data.walker_id)
        .where(AccelerometerData.timestamp >= five_seconds_ago)
        .order_by(desc(AccelerometerData.timestamp))
    )
    recent_entries = result.scalars().all()

    # 움직임 판단 로직 - 정지 상태 더 엄격하게 판단
    is_moving = 0
    zero_count = 0
    
    # 확실한 움직임 임계값을 더 높게 설정
    if accel_value >= 0.08:
        is_moving = 1
    else:
        # 0.08 미만일 때는 매우 엄격하게 판단
        if recent_entries:
            recent_moving_count = sum(1 for e in recent_entries if e.is_moving == 1)
            recent_zero_count = sum(1 for e in recent_entries if e.is_moving == 0)
            zero_count = recent_zero_count
            
            # 현재 값이 0.04 미만이면 거의 확실히 정지 (강제 정지)
            if accel_value < 0.04:
                is_moving = 0
            # 현재 값이 0.04~0.06 사이면 매우 엄격하게 판단
            elif accel_value < 0.06:
                # 과거 데이터가 모두 1이더라도 현재 값이 낮으면 정지로 강제 전환
                if recent_zero_count == 0:  # 과거에 0이 없으면
                    is_moving = 0  # 강제로 정지 상태 시작
                else:
                    # 최근 1개라도 0이면 정지
                    last_1_entry = recent_entries[:1]
                    if last_1_entry and last_1_entry[0].is_moving == 0:
                        is_moving = 0
                    else:
                        is_moving = 1
            # 현재 값이 0.06~0.08 사이면 연속성으로 판단하되 엄격하게
            else:
                # 최근 2개 중 1개라도 0이면 정지
                last_2_entries = recent_entries[:2]
                last_2_zeros = sum(1 for e in last_2_entries if e.is_moving == 0)
                if last_2_zeros >= 1:
                    is_moving = 0
                else:
                    is_moving = 1
        else:
            # 최근 데이터가 없으면 0.06 미만일 때만 정지
            if accel_value < 0.06:
                is_moving = 0
            else:
                is_moving = 1

    # 활동 시간 저장 (움직임이 감지된 경우에만)
    if is_moving == 1:
        today = now.date()
        result = await db.execute(
            select(ActivityDuration)
            .where(ActivityDuration.user_id == data.user_id)
            .where(ActivityDuration.walker_id == data.walker_id)
            .where(ActivityDuration.date == today)
        )
        duration_entry = result.scalar_one_or_none()

        if duration_entry:
            duration_entry.total_seconds += 1
        else:
            duration_entry = ActivityDuration(
                user_id=data.user_id,
                walker_id=data.walker_id,
                date=today,
                total_seconds=1
            )
            db.add(duration_entry)

        await db.commit()

    # accelerometer 데이터 저장
    entry = AccelerometerData(
        user_id=data.user_id,
        walker_id=data.walker_id,
        accel_value=accel_value,
        ax=data.ax,
        ay=data.ay,
        az=data.az,
        is_moving=is_moving,
        pitch=data.pitch,
        slope=data.slope,
        timestamp=now
    )

    db.add(entry)
    if data.slope == "낙상":
        print(f"🚨 낙상 감지됨! 사용자: {data.user_id}, 워커: {data.walker_id}, 시간: {now}")
    
    await db.commit()
    
    print(f"DEBUG - accel_value: {accel_value:.3f}, is_moving: {is_moving}, zero_count: {zero_count}")

    return {
        "message": " 센서 데이터 저장 완료",
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