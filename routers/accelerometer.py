# accelerometer.py
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

    # ---------------------------
    # 움직임 판단 로직 (튜닝 상수)
    # ---------------------------
    HARD_MOVE_THRESH = 0.060   # 이 값 이상이면 즉시 '움직임'
    SOFT_BAND_LOW    = 0.030   # 애매 구간 하한
    SOFT_BAND_HIGH   = 0.060   # 애매 구간 상한

    # 통계 기반 판정 임계값 (최근 값들로 계산)
    STD_THRESH       = 0.012   # 표준편차 임계
    RANGE_THRESH     = 0.035   # (max-min) 임계
    MAXDIFF_THRESH   = 0.020   # 인접 샘플 간 최대 차이 임계

    # 스파이크 무시 임계
    SPIKE_ABS        = 0.150   # 이 값 이상이면 스파이크 후보 (예: 0.205)
    SPIKE_NEIGH_DIFF = 0.100   # 이웃과 차이가 너무 크면 스파이크 의심

    # 최근 값 수집 (오래된 -> 최신 순 정렬)
    values = [e.accel_value for e in recent_entries[:7]]
    values.reverse()
    values.append(accel_value)

    is_moving = 0

    # 1) 하드 임계로 빠른 판정
    if accel_value >= HARD_MOVE_THRESH:
        is_moving = 1
        print(f"DEBUG - 즉시 움직임: accel={accel_value:.5f} (>= {HARD_MOVE_THRESH})")

        # 1-1) 스파이크 필터: 주변이 너무 조용하면 단발 스파이크로 무시
        if len(values) >= 3 and accel_value >= SPIKE_ABS:
            prev_v = values[-2]
            if abs(accel_value - prev_v) >= SPIKE_NEIGH_DIFF:
                # 이전/주변이 잔잔하면 스파이크로 의심
                mean_v = sum(values) / len(values)
                local_std = (sum((v - mean_v) ** 2 for v in values) / len(values)) ** 0.5
                local_rng = max(values) - min(values)
                if local_std < STD_THRESH and local_rng < RANGE_THRESH:
                    is_moving = 0
                    print(f"DEBUG - 스파이크 무시: spike={accel_value:.5f}, prev={prev_v:.5f}, std={local_std:.5f}, rng={local_rng:.5f}")

    else:
        # 2) 애매 구간: 통계 기반 판정
        if accel_value <= SOFT_BAND_LOW:
            is_moving = 0
            print(f"DEBUG - 저신호 정지: accel={accel_value:.5f} (<= {SOFT_BAND_LOW})")
        else:
            win = values[-8:] if len(values) >= 8 else values
            if len(win) >= 3:
                mean_v = sum(win) / len(win)
                diffs = [abs(win[i] - win[i - 1]) for i in range(1, len(win))]
                std = (sum((v - mean_v) ** 2 for v in win) / len(win)) ** 0.5
                rng = max(win) - min(win)
                maxdiff = max(diffs) if diffs else 0.0

                if (std >= STD_THRESH) or (rng >= RANGE_THRESH) or (maxdiff >= MAXDIFF_THRESH):
                    is_moving = 1
                    print(f"DEBUG - 통계 기반 움직임: std={std:.5f} rng={rng:.5f} maxdiff={maxdiff:.5f}")
                else:
                    is_moving = 0
                    print(f"DEBUG - 통계 기반 정지: std={std:.5f} rng={rng:.5f} maxdiff={maxdiff:.5f}")
            else:
                # 데이터가 적으면 보수적으로 중간값 기준
                mid = (SOFT_BAND_LOW + SOFT_BAND_HIGH) / 2
                is_moving = 1 if accel_value >= mid else 0
                print(f"DEBUG - 샘플부족 보수판정: accel={accel_value:.5f}, mid={mid:.5f} -> is_moving={is_moving}")

    # 활동 시간 누적 (움직임일 때만 1초 가산)
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

    # 여기서 flush로 INSERT를 DB에 반영(커밋은 아님) → 같은 트랜잭션 내 집계에 포함
    await db.flush()

    # 🚨 낙상 태그가 들어오면 자동 감지 실행
    fall_alert_created = False
    if data.slope == "낙상":
        print(f"🚨 낙상 감지됨! 사용자: {data.user_id}, 워커: {data.walker_id}, 시간: {now}")
        fall_alert_created = await check_fall_detection(data.user_id, data.walker_id, db)
        if fall_alert_created:
            print("✅ 낙상 알림 자동 생성 완료!")
        else:
            print("⚠️ 낙상 감지 기준 미충족")

    # 마지막에 한 번만 커밋
    await db.commit()

    print(f"DEBUG - Final: accel_value={accel_value:.5f}, is_moving={is_moving}")

    return {
        "message": "센서 데이터 저장 완료",
        "accel_value": round(accel_value, 3),
        "is_moving": is_moving,
        "fall_alert_created": fall_alert_created,
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
