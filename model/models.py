from sqlalchemy import Column, DateTime, String, Integer, Float, TIMESTAMP
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, TIMESTAMP, ForeignKey, Date
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Float, TIMESTAMP
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import DateTime
from sqlalchemy import Boolean

Base = declarative_base()


# GPS 데이터 테이블
class GPSData(Base):
    __tablename__ = "gps_data"
    
    id = Column(Integer, primary_key=True, autoincrement=True)  #  자동 증가
    user_id = Column(String(100), ForeignKey("users.user_id"))  # users 테이블 참조
    latitude = Column(Float, nullable=False) #  위도
    longitude = Column(Float, nullable=False)  #  경도
    timestamp = Column(TIMESTAMP, default=func.now(), nullable=False)  # 타임스탬프 기본값

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


# Walkers 테이블
class Walker(Base):
    __tablename__ = "walkers"
    walker_id = Column(String(100), primary_key=True)
    brake_status = Column(String(10))

# Obstacles 테이블
class ObstacleData(Base):
    __tablename__ = "obstacles"
    obstacle_id = Column(String(100), primary_key=True)
    user_id = Column(String(100), ForeignKey("users.user_id"))  # users 테이블 참조
    obstacle_type = Column(String(100))
    detection_time = Column(TIMESTAMP)
    walker_id = Column(String(100))
    is_detected = Column(Integer)  # 1(감지됨), 0(감지 안됨)
    alert_level = Column(String(20), nullable=True)  
    risk_score = Column(Float, nullable=True)
    
 

# 활동 로그 테이블
class Activity(Base):
    __tablename__ = "activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    walker_id = Column(String(100), ForeignKey("walkers.walker_id"), nullable=False)
    start_time = Column(TIMESTAMP, nullable=False, default=func.now())
    end_time = Column(TIMESTAMP, nullable=True)
    duration = Column(Integer, default=0)  # 활동 시간 (분)

# Crack 감지 데이터 테이블
class CrackData(Base):
    __tablename__ = "crack"

    crack_id = Column(String(100), primary_key=True)  # UUID 기반 고유 ID
    user_id = Column(String(100), ForeignKey("users.user_id"))  # 사용자 참조
    crack_type = Column(String(100))  # 감지된 crack 종류 (클래스 이름)
    detection_time = Column(TIMESTAMP, default=func.now())  # 감지 시간
    walker_id = Column(String(100), ForeignKey("walkers.walker_id"))  #  워커 참조
    is_detected = Column(Integer)  # 1(감지됨), 0(감지 안됨)
    
# Accelerometer 데이터 테이블
class AccelerometerData(Base):
    __tablename__ = "accelerometer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    walker_id = Column(String(100), ForeignKey("walkers.walker_id"), nullable=False)

    accel_value = Column(Float, nullable=False)
    ax = Column(Float)  # ← 추가
    ay = Column(Float)  # ← 추가
    az = Column(Float)  # ← 추가

    is_moving = Column(Integer, default=0)
    pitch = Column(Float)
    slope = Column(String(20))
    timestamp = Column(TIMESTAMP, default=func.now())

# ActivityDuration 테이블
class ActivityDuration(Base):
    __tablename__ = "activity_duration"
    id = Column(Integer, primary_key=True)
    user_id = Column(String)
    walker_id = Column(String)
    date = Column(Date)
    total_seconds = Column(Integer)  # 하루 누적 활동 시간 (초)



# 낙상 알림 테이블
class FallAlert(Base):
    __tablename__ = "fall_alerts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), ForeignKey("users.user_id"), nullable=False)
    walker_id = Column(String(100), ForeignKey("walkers.walker_id"), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime, nullable=True)
    dashboard_response = Column(String, nullable=True)  # "turned_off" / "not_turned_off"

    response_timestamp = Column(DateTime, nullable=True)
