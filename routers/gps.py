from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime
from pydantic import BaseModel, Field
from geopy.distance import geodesic  # ✅ 거리 계산용 라이브러리 추가
import pytz
from model.models import GPSData
from database import get_db

router = APIRouter()

# ✅ GPS 데이터 Pydantic 모델
class GPSDataCreate(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timestamp: datetime

@router.post("/gps/{user_id}")
async def create_gps_entry(data: GPSDataCreate, db: AsyncSession = Depends(get_db)):
    try:
        print(f"Received GPS Data: {data.dict()}")  

        if data.timestamp.tzinfo is not None:
            data.timestamp = data.timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        # ✅ 가장 최근 GPS 데이터 가져오기
        query = select(GPSData).order_by(GPSData.timestamp.desc()).limit(1)
        result = await db.execute(query)
        last_gps = result.scalars().first()

        # ✅ 이동 거리 계산 (이전 위치가 있을 경우)
        distance_moved = 0  # 초기값
        if last_gps:
            prev_location = (last_gps.latitude, last_gps.longitude)
            new_location = (data.latitude, data.longitude)
            distance_moved = geodesic(prev_location, new_location).meters  # 🚀 이동 거리(m) 계산
            print(f"Moved Distance: {distance_moved}m")

        # ✅ 새 GPS 데이터 저장
        new_entry = GPSData(
            latitude=data.latitude,
            longitude=data.longitude,
            timestamp=data.timestamp
        )
        db.add(new_entry)
        await db.flush()
        await db.commit()
        await db.refresh(new_entry)

        return {
            "message": "GPS data recorded successfully",
            "distance_moved": distance_moved
        }
    
    except Exception as e:
        await db.rollback()
        print(f"Database Commit Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database Commit Error: {str(e)}")
