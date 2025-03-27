from sqlalchemy import Column, String, Integer, Float, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Float, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

# GPS 데이터 테이블
class GPSData(Base):
    __tablename__ = "gps_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)  # ✅ 자동 증가
    user_id = Column(String(100), ForeignKey("users.user_id"))  # users 테이블 참조
    latitude = Column(Float, nullable=False)  # ✅ 위도
    longitude = Column(Float, nullable=False)  # ✅ 경도
    timestamp = Column(TIMESTAMP, default=func.now(), nullable=False)  # ✅ 타임스탬프 기본값

# 심박수 테이블
class HeartRate(Base):
    __tablename__ = "heartrate"
    id = Column(Integer, primary_key=True, autoincrement=True)  # 고유한 심박수 레코드 ID
    user_id = Column(String(100), ForeignKey("users.user_id"))  # users 테이블 참조
    heartrate = Column(Integer, nullable=False)  # 심박수 값
    recorded_at = Column(TIMESTAMP, server_default=func.now())  # 데이터 기록 시간


# Users 테이블
class User(Base):
    __tablename__ = "users"
    user_id = Column(String(100), primary_key=True)
    name = Column(String(25))
    contact = Column(String(25))
    birth = Column(String(25))

# Guardians 테이블
class Guardian(Base):
    __tablename__ = "guardians"
    guardian_id = Column(String(100), primary_key=True)
    name = Column(String(25))
    contact = Column(String(25))
    birth = Column(String(25))
    user_id = Column(String(100))

# Healthcare 테이블
class Healthcare(Base):
    __tablename__ = "healthcare"
    healthcare_id = Column(String(100), primary_key=True)
    heartrate = Column(Integer)
    activity_time = Column(Integer)
    calory = Column(Float)
    travel_distance = Column(String(25))
    user_id = Column(String(100))
    # walker_id = Column(String(100))

# Walkers 테이블
class Walker(Base):
    __tablename__ = "walkers"
    walker_id = Column(String(100), primary_key=True)
    brake_status = Column(String(10))

# Obstacles 테이블
class Obstacle(Base):
    __tablename__ = "obstacles"
    obstacle_id = Column(String(100), primary_key=True)
    obstacle_type = Column(String(100))
    detection_time = Column(TIMESTAMP)
    walker_id = Column(String(100))
