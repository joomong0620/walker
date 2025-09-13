from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from pydantic import BaseModel, Field
from geopy.distance import geodesic
import pytz

from model.models import GPSData
from database import get_db

router = APIRouter()

#  Pydantic 모델
class GPSDataCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime

#  GPS 데이터 저장
@router.post("/gps/{user_id}")
async def create_gps_entry(user_id: str, data: GPSDataCreate, db: AsyncSession = Depends(get_db)):
    try:
        print(f"📥 Received GPS Data from {user_id}: {data.dict()}")

        # UTC로 타임스탬프 변환
        if data.timestamp.tzinfo is not None:
            data.timestamp = data.timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        # 가장 최근 user_id의 GPS 데이터 조회
        query = (
            select(GPSData)
            .where(GPSData.user_id == user_id)
            .order_by(GPSData.timestamp.desc())
            .limit(1)
        )
        result = await db.execute(query)
        last_gps = result.scalars().first()

        # 거리 계산
        distance_moved = 0
        prev_location = None
        new_location = (data.latitude, data.longitude)

        if last_gps:
            prev_location = (last_gps.latitude, last_gps.longitude)
            distance_moved = geodesic(prev_location, new_location).meters
            print(f"📍 From {prev_location} → To {new_location} | Distance: {distance_moved:.2f}m")

        # 새 데이터 저장
        new_entry = GPSData(
            user_id=user_id,
            latitude=data.latitude,
            longitude=data.longitude,
            timestamp=data.timestamp
        )
        db.add(new_entry)
        await db.commit()
        await db.refresh(new_entry)

        return {
            "message": "GPS data recorded successfully",
            "user_id": user_id,
            "prev_location": prev_location,
            "new_location": new_location,
            "distance_moved": distance_moved
        }

    except Exception as e:
        await db.rollback()
        print(f"❌ Database Commit Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database Commit Error: {str(e)}")

@router.get("/gps/{user_id}")
async def get_latest_gps_by_user(user_id: str, db: AsyncSession = Depends(get_db)):
    # 최근 2개의 위치를 불러온다
    query = (
        select(GPSData)
        .where(GPSData.user_id == user_id)
        .order_by(GPSData.timestamp.desc())
        .limit(2)
    )
    result = await db.execute(query)
    records = result.scalars().all()

    if not records:
        raise HTTPException(status_code=404, detail="No GPS data found for this user")

    latest = records[0]
    distance_moved = 0
    prev_location = None

    if len(records) > 1:
        prev_location = (records[1].latitude, records[1].longitude)
        current_location = (latest.latitude, latest.longitude)
        distance_moved = geodesic(prev_location, current_location).meters

    return {
        "user_id": latest.user_id,
        "latitude": latest.latitude,
        "longitude": latest.longitude,
        "timestamp": latest.timestamp,
        "distance_moved": distance_moved,
        "prev_location": prev_location,
    }

