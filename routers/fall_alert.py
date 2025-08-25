# fall_alert.py
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from database import get_db
from model.models import FallAlert, AccelerometerData
from pydantic import BaseModel
from datetime import datetime, timedelta
import os

from utils.sms import send_sms_sync

router = APIRouter()

class DashboardResponse(BaseModel):
    action: str  # "turned_off" 또는 "not_turned_off"

WINDOW_SECONDS = 20
FALL_THRESH = 15

async def check_fall_detection(user_id: str, walker_id: str, db: AsyncSession):
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=WINDOW_SECONDS)

    cnt = (await db.execute(
        select(func.count())
        .select_from(AccelerometerData)
        .where(AccelerometerData.user_id == user_id)
        .where(AccelerometerData.walker_id == walker_id)
        .where(AccelerometerData.timestamp >= window_start)
        .where(AccelerometerData.slope == "낙상")
    )).scalar_one()

    if cnt >= FALL_THRESH:
        alert = FallAlert(
            user_id=user_id, walker_id=walker_id,
            timestamp=now, resolved=False,
            dashboard_response=None, response_timestamp=None
        )
        db.add(alert)
        await db.flush()  # alert.id 확보
        print(f"🚨 낙상 알림 자동 등록! {user_id}/{walker_id}, cnt={cnt} (win {WINDOW_SECONDS}s)")
        return True

    print(f"ℹ️ 낙상 기준 미충족: cnt={cnt}/{FALL_THRESH} (win {WINDOW_SECONDS}s)")
    return False

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
        .where(FallAlert.dashboard_response == None)
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
        return {"fall_detected": False, "alert_id": None}

@router.post("/fall-alert/dashboard-response")
async def receive_dashboard_response(
    data: DashboardResponse,
    user_id: str = Query(...),
    walker_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
    bg: BackgroundTasks = None
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

    if data.action not in ["turned_off", "not_turned_off"]:
        return {"message": "잘못된 응답입니다. 'turned_off' 또는 'not_turned_off'만 가능합니다.", "success": False}

    # 1) DB 상태 반영
    alert.dashboard_response = data.action
    alert.response_timestamp = now
    alert.resolved = True

    # 2) not_turned_off 이면 문자 발송 예약
    if data.action == "not_turned_off" and bg is not None:
        # 수신번호 목록: 환경변수 ALERT_PHONES="01011112222,01033334444" 형태
        raw = os.getenv("ALERT_PHONES", "")
        # 비었으면 본인 발신번호로라도 받도록 fallback
        if not raw:
            raw = os.getenv("SMS_FROM", "")

        targets = [p.strip() for p in raw.split(",") if p.strip()]
        if targets:
            ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")
            text = (
                f"[낙상 미해결 알림]\n"
                f"사용자:{user_id}\n기기:{walker_id}\n발생:{alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
                f"대시보드 응답: 보호자가 알림을 끄지 않음(not_turned_off)\n"
                f"확인이 필요합니다. ({ts})"
            )
            for to in targets:
                bg.add_task(send_sms_sync, to, text)

    await db.commit()

    return {
        "message": f"대시보드 응답이 저장되었습니다: {data.action}",
        "success": True,
        "action": data.action
    }

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
