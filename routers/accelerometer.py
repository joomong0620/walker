# accelerometer.py 수정 - receive_from_hardware 함수 업데이트

from fastapi import APIRouter, Depends, Query
from routers.fall_alert import check_fall_detection  # 이미 import되어 있음
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from database import get_db
from model.models import AccelerometerData, ActivityDuration
from pydantic import BaseModel
import math

router = APIRouter()

class AccelRequest(BaseModel):
    user_id: str
    walker_id: str
    ax: float
    ay: float
    az: float
    pitch: float
    slope: str

@router.post("/accelerometer/")
async def receive_from_hardware(
    data: AccelRequest,
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()
    accel_value = math.sqrt(data.ax ** 2 + data.ay ** 2 + data.az ** 2)

    eight_seconds_ago = now - timedelta(seconds=8)
    result = await db.execute(
        select(AccelerometerData)
        .where(AccelerometerData.user_id == data.user_id)
        .where(AccelerometerData.walker_id == data.walker_id)
        .where(AccelerometerData.timestamp >= eight_seconds_ago)
        .order_by(desc(AccelerometerData.timestamp))
    )
    recent_entries = result.scalars().all()

    is_moving = 0

    # 기준값 범위 재조정 (실제 평지 가속값 0.94~0.98 근처)
    if accel_value <= 0.98:
        is_moving = 0
        print(f"DEBUG - 정지: accel_value={accel_value:.3f}")
    elif accel_value >= 1.02:
        is_moving = 1
        print(f"DEBUG - 움직임: accel_value={accel_value:.3f}")
    else:
        # 0.98~1.02 사이 애매한 값일 경우 과거 분석
        values = [entry.accel_value for entry in recent_entries[:5]]
        values.append(accel_value)

        if len(values) >= 2:
            diffs = [abs(values[i] - values[i-1]) for i in range(1, len(values))]
            std = math.sqrt(sum((v - sum(values)/len(values))**2 for v in values) / len(values))
            rng = max(values) - min(values)

            if max(diffs) < 0.002 and std < 0.002 and rng < 0.005:
                is_moving = 0
                print(f"DEBUG - 정지 판단 (평균 변화량 기준): std={std:.5f}, range={rng:.5f}")
            else:
                is_moving = 1
                print(f"DEBUG - 움직임 판단 (미세 변화 감지): std={std:.5f}, range={rng:.5f}")

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

    # 가속도계 데이터 저장
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
    await db.commit()

    # 🚨 여기가 핵심! 낙상 데이터가 들어오면 자동 감지 실행
    fall_alert_created = False
    if data.slope == "낙상":
        print(f"🚨 낙상 감지됨! 사용자: {data.user_id}, 워커: {data.walker_id}, 시간: {now}")
        
        # 낙상 자동 감지 함수 호출
        fall_alert_created = await check_fall_detection(data.user_id, data.walker_id, db)
        
        if fall_alert_created:
            print(f"✅ 낙상 알림 자동 생성 완료!")
        else:
            print(f"⚠️ 낙상 감지 조건 미충족 또는 이미 활성 알림 존재")

    print(f"DEBUG - Final: accel_value={accel_value:.3f}, is_moving={is_moving}")
    
    return {
        "message": "센서 데이터 저장 완료",
        "accel_value": round(accel_value, 3),
        "is_moving": is_moving,
        "fall_alert_created": fall_alert_created,  # 낙상 알림 생성 여부 추가
        "timestamp": now.isoformat()
    }


# 나머지 코드는 그대로...
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