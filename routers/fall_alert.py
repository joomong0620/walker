# fall_alert.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database import get_db
from model.models import FallAlert, AccelerometerData
from datetime import datetime, timedelta

router = APIRouter()

# ------------------------
# POST: 센서 데이터 수신 → 낙상 자동 감지
# ------------------------
@router.post("/accelerometer/fall-detect")
async def receive_accel_and_check_fall(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=20)

    # 최근 20초간 낙상 slope 데이터 조회
    result = await db.execute(
        select(AccelerometerData)
        .where(AccelerometerData.user_id == user_id)
        .where(AccelerometerData.walker_id == walker_id)
        .where(AccelerometerData.timestamp >= window_start)
        .where(AccelerometerData.slope == "낙상")
    )
    fall_entries = result.scalars().all()

    # 알림 이미 존재하는지 확인
    if len(fall_entries) >= 20:
        existing_alert_result = await db.execute(
            select(FallAlert)
            .where(FallAlert.user_id == user_id)
            .where(FallAlert.walker_id == walker_id)
            .where(FallAlert.resolved == False)
        )
        existing_alert = existing_alert_result.scalar_one_or_none()

        if not existing_alert:
            alert = FallAlert(
                user_id=user_id,
                walker_id=walker_id,
                timestamp=now,
                resolved=False
            )
            db.add(alert)
            await db.commit()
            return {"message": "자동 낙상 알림 등록 완료"}
        else:
            return {"message": "이미 활성화된 낙상 알림이 있습니다."}

    return {"message": "낙상 감지 기준 미충족", "count": len(fall_entries)}

# ------------------------
# POST: 대시보드 → 낙상 감지 알림 수동 전송
# ------------------------
@router.post("/fall-alert/")
async def send_fall_alert(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()

    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == False)
        .order_by(desc(FallAlert.timestamp))
    )
    active_alert = result.scalar_one_or_none()

    if active_alert:
        return {"message": "이미 활성화된 낙상 알림이 있습니다."}

    alert = FallAlert(
        user_id=user_id,
        walker_id=walker_id,
        timestamp=now,
        resolved=False
    )
    db.add(alert)
    await db.commit()
    return {"message": "낙상 알림 등록 완료"}

# ------------------------
# POST: 보호자가 알림을 해제함
# ------------------------
@router.post("/fall-alert/resolve")
async def resolve_fall_alert(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == False)
        .order_by(desc(FallAlert.timestamp))
    )
    alert = result.scalar_one_or_none()

    if alert:
        alert.resolved = True
        alert.resolved_at = datetime.utcnow()
        await db.commit()
        return {"message": "낙상 알림이 해제되었습니다."}
    return {"message": "활성화된 낙상 알림이 없습니다."}

# ------------------------
# GET: 보호자 앱 → 낙상 알림 조회 (5초마다)
# ------------------------
@router.get("/fall-alert/check")
async def check_fall_alert(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == False)
        .order_by(desc(FallAlert.timestamp))
    )
    alert = result.scalar_one_or_none()

    if alert:
        return {
            "fall_detected": True,
            "timestamp": alert.timestamp.isoformat(),
        }
    return {"fall_detected": False}

# ------------------------
# POST: 테스트용 낙상 데이터 20개 삽입
# ------------------------
@router.post("/test/fall-dummy")
async def insert_fall_dummy(
    
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
    
):
    user_id = user_id.strip()
    walker_id = walker_id.strip()
    
    now = datetime.utcnow()
    for i in range(20):
        entry = AccelerometerData(
            user_id=user_id,
            walker_id=walker_id,
            accel_value=0.4 + i * 0.01,
            ax=0.1,
            ay=0.2,
            az=0.3,
            is_moving=1,
            pitch=15.0,
            slope="낙상",
            timestamp=now - timedelta(seconds=20 - i)
        )
        db.add(entry)
    await db.commit()
    return {"message": "테스트용 낙상 데이터 20개 삽입 완료", "user_id": user_id, "walker_id": walker_id}
