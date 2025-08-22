# fall_alert.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database import get_db
from model.models import FallAlert, AccelerometerData
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone

router = APIRouter()

# 요청 모델
class DashboardResponse(BaseModel):
    action: str  # "turned_off" 또는 "not_turned_off"

# 설정: 최근 20초 내 낙상 15회면 즉시 생성
WINDOW_SECONDS = 20
FALL_THRESH = 15

# 낙상 자동 감지 함수 (가속도계 데이터 저장 시 호출)
async def check_fall_detection(user_id: str, walker_id: str, db: AsyncSession):
    """
    최근 20초간 낙상 slope가 15번 이상이면 즉시 낙상 알림 등록
    - 기존 '이미 활성 알림 존재' 여부는 보지 않고 무조건 생성
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=WINDOW_SECONDS)

    # 최근 WINDOW_SECONDS 동안 낙상 카운트 (COUNT 쿼리)
    cnt_q = (
        select(func.count())
        .select_from(AccelerometerData)
        .where(AccelerometerData.user_id == user_id)
        .where(AccelerometerData.walker_id == walker_id)
        .where(AccelerometerData.timestamp >= window_start)
        .where(AccelerometerData.slope == "낙상")
    )
    fall_count = (await db.execute(cnt_q)).scalar_one()

    if fall_count >= FALL_THRESH:
        alert = FallAlert(
            user_id=user_id,
            walker_id=walker_id,
            timestamp=now,
            resolved=False,
            dashboard_response=None,
            response_timestamp=None
        )
        db.add(alert)
        # 여기서는 commit하지 않고, 호출 측에서 함께 커밋(동일 트랜잭션 유지)
        await db.flush()
        print(f"🚨 낙상 알림 자동 등록! {user_id}/{walker_id}, cnt={fall_count} (win {WINDOW_SECONDS}s)")
        return True

    print(f"ℹ️ 낙상 기준 미충족: cnt={fall_count}/{FALL_THRESH} (win {WINDOW_SECONDS}s)")
    return False


# GET: 대시보드 폴링
@router.get("/fall-alert/dashboard")
async def get_fall_alert_for_dashboard(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
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

# POST: 대시보드에서 보호자 응답 전송
@router.post("/fall-alert/dashboard-response")
async def receive_dashboard_response(
    data: DashboardResponse,
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
        .where(FallAlert.dashboard_response == None)
        .order_by(desc(FallAlert.timestamp))
    )
    alert = result.scalar_one_or_none()

    if not alert:
        return {"message": "응답할 낙상 알림이 없습니다.", "success": False}

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

# GET: 앱 폴링
@router.get("/fall-alert/app")
async def get_fall_alert_for_app(
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
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
