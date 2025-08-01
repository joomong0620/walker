# fall_alert.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database import get_db
from model.models import FallAlert, AccelerometerData
from datetime import datetime, timedelta
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

now = datetime.now(KST)  # 한국 시간

router = APIRouter()

# ------------------------
# 요청 모델
# ------------------------
class DashboardResponse(BaseModel):
    action: str  # "turned_off" 또는 "not_turned_off"

# ------------------------
# 낙상 자동 감지 함수 (가속도계 데이터 저장 시 호출)
# ------------------------
async def check_fall_detection(user_id: str, walker_id: str, db: AsyncSession):
    """
    최근 20초간 낙상 slope가 15번 이상이면 낙상 알림 등록
    """
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

    # 낙상 감지 기준: 20초 안에 15번 이상
    if len(fall_entries) >= 15:
        # 이미 활성화된 알림이 있는지 확인
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
                resolved=False,
                dashboard_response=None,  # 대시보드 응답 대기 중
                response_timestamp=None   # 응답 시간
            )
            db.add(alert)
            await db.commit()
            print(f"🚨 낙상 알림 자동 등록! 사용자: {user_id}, 워커: {walker_id}, 낙상 횟수: {len(fall_entries)}")
            return True
        else:
            print(f"⚠️ 이미 활성화된 낙상 알림 존재: {user_id}, {walker_id}")
            return False

    return False

# ------------------------
# GET: 대시보드에서 낙상 알림 확인 (폴링용)
# ------------------------
@router.get("/fall-alert/dashboard")
async def get_fall_alert_for_dashboard(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 대시보드 응답 대기 중인 알림 조회
    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == False)
        .where(FallAlert.dashboard_response == None)  # 아직 대시보드에서 응답 안함
        .order_by(desc(FallAlert.timestamp))
    )
    alert = result.scalar_one_or_none()

    if alert:
        return {
            "fall_detected": True,
            "timestamp": alert.timestamp.isoformat(),
            "alert_id": alert.id
        }
    else:
        return {
            "fall_detected": False,
            "alert_id": None
        }

# ------------------------
# POST: 대시보드에서 보호자 응답 전송 (껐다/안껐다)
# ------------------------
@router.post("/fall-alert/dashboard-response")
async def receive_dashboard_response(
    data: DashboardResponse,
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    now = datetime.utcnow()
    
    # 응답 대기 중인 알림 조회
    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == False)
        .where(FallAlert.dashboard_response == None)
        .order_by(desc(FallAlert.timestamp))
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return {"message": "응답할 낙상 알림이 없습니다.", "success": False}

    # 응답 처리 (1분 체크 없이 바로 저장)
    if data.action in ["turned_off", "not_turned_off"]:
        alert.dashboard_response = data.action
        alert.response_timestamp = now
        alert.resolved = True
        await db.commit()
        
        return {
            "message": f"대시보드 응답이 저장되었습니다: {data.action}",
            "success": True,
            "action": data.action
        }
    else:
        return {
            "message": "잘못된 응답입니다. 'turned_off' 또는 'not_turned_off'만 가능합니다.",
            "success": False
        }

# ------------------------
# GET: 앱에서 낙상 알림 결과 조회 (폴링용)
# ------------------------
@router.get("/fall-alert/app")
async def get_fall_alert_for_app(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # 최근 해결된 알림 중에서 대시보드 응답이 있는 것 조회
    result = await db.execute(
        select(FallAlert)
        .where(FallAlert.user_id == user_id)
        .where(FallAlert.walker_id == walker_id)
        .where(FallAlert.resolved == True)
        .where(FallAlert.dashboard_response != None)
        .order_by(desc(FallAlert.response_timestamp))
        .limit(1)
    )
    alert = result.scalar_one_or_none()

    if alert:
        return {
            "has_result": True,
            "fall_timestamp": alert.timestamp.isoformat(),
            "response_timestamp": alert.response_timestamp.isoformat() if alert.response_timestamp else None,
            "dashboard_response": alert.dashboard_response,
            "alert_id": alert.id,
            "response_message": "보호자가 알림을 껐습니다." if alert.dashboard_response == "turned_off" else "보호자가 알림을 끄지 않았습니다."
        }
    else:
        return {
            "has_result": False,
            "fall_timestamp": None,
            "response_timestamp": None,
            "dashboard_response": None,
            "alert_id": None,
            "response_message": "처리된 낙상 알림이 없습니다."
        }

