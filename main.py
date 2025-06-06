import os
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['DISPLAY'] = ':99'

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
logger.info(f"Database URL: {'SET' if DATABASE_URL else 'NOT SET'}")

# 데이터베이스 관련 임포트 (조건부)
db_available = False
if DATABASE_URL:
    try:
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.future import select
        from sqlalchemy import update, delete
        from model.models import Base, User, Guardian
        from utils import sqlalchemy_to_dict
        
        # SQLAlchemy 비동기 엔진 및 세션 설정
        engine = create_async_engine(DATABASE_URL, echo=True)
        async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        db_available = True
        logger.info("Database connection configured successfully")
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        db_available = False

# 라우터 임포트 (선택적)
try:
    from routers.activity import router as activity_router
    from routers.heartrate import router as heartrate_router
    from routers.gps import router as gps_router
    from routers.obstacle import router as obstacle_router
    from routers.pothole import router as pothole_router
    from routers.accelerometer import router as accelerometer_router
    from routers.obstacle_ws_router import obstacle_ws_router 
    from routers.profile import router as profile_router
    from routers.report import router as report_router
    routers_available = True
except ImportError as e:
    logger.warning(f"Some routers not available: {e}")
    routers_available = False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """안전한 애플리케이션 시작/종료 처리"""
    logger.info("🚀 Starting Walker API...")
    
    # 데이터베이스 초기화 (사용 가능한 경우에만)
    if db_available:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("✅ Database tables created successfully")
        except Exception as e:
            logger.error(f"❌ Database initialization failed: {e}")
    else:
        logger.info("⚠️ Running without database")
    
    logger.info("✅ Application startup completed")
    yield
    logger.info("🛑 Application shutdown")

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Walker API",
    description="Walker 보행자 안전 시스템 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "*"  # 개발용 - 프로덕션에서는 구체적인 도메인 지정
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 기본 라우트
@app.get("/")
async def root():
    return {
        "message": "Walker API is running!",
        "status": "healthy",
        "database": "connected" if db_available else "not configured",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": db_available,
        "timestamp": os.environ.get("RAILWAY_DEPLOYMENT_ID", "local")
    }

# WebSocket 테스트 엔드포인트
@app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    await websocket.accept()
    logger.info("🔌 WebSocket 연결됨")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"📩 받은 메시지: {data}")
            await websocket.send_text(f"💬 서버가 받은 메시지: {data}")
    except WebSocketDisconnect:
        logger.info("❌ WebSocket 연결 끊김")

# 데이터베이스 의존성 (데이터베이스가 있는 경우에만)
async def get_db():
    if not db_available:
        raise HTTPException(status_code=503, detail="Database not available")
    
    async with async_session() as session:
        yield session

# Pydantic 모델들
class UserCreate(BaseModel):
    user_id: str
    name: str
    contact: str
    birth: str

    class Config:
        from_attributes = True  # Pydantic V2 호환

class UserResponse(BaseModel):
    user_id: str
    name: str
    contact: str
    birth: str

    class Config:
        from_attributes = True

class GuardianCreate(BaseModel):
    guardian_id: str
    name: str
    contact: str
    birth: str
    user_id: str

    class Config:
        from_attributes = True

class GuardianResponse(BaseModel):
    guardian_id: str
    name: str
    contact: str
    birth: str
    user_id: str

    class Config:
        from_attributes = True

# 데이터베이스 라우트 (데이터베이스가 있는 경우에만 활성화)
if db_available:
    # 사용자 관련 엔드포인트
    @app.post("/users/", response_model=UserResponse)
    async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
        existing_user = await db.execute(select(User).where(User.user_id == user.user_id))
        if existing_user.scalar():
            raise HTTPException(status_code=400, detail="User already exists")

        new_user = User(user_id=user.user_id, name=user.name, contact=user.contact, birth=user.birth)
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @app.get("/users/", response_model=list[UserResponse])
    async def read_users(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User))
        users = result.scalars().all()
        return users

    @app.get("/users/{user_id}", response_model=UserResponse)
    async def read_user(user_id: str, db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    # 보호자 관련 엔드포인트
    @app.post("/guardians/", response_model=GuardianResponse)
    async def create_guardian(guardian: GuardianCreate, db: AsyncSession = Depends(get_db)):
        existing_guardian = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian.guardian_id))
        if existing_guardian.scalar():
            raise HTTPException(status_code=400, detail="Guardian already exists")

        new_guardian = Guardian(
            guardian_id=guardian.guardian_id,
            name=guardian.name,
            contact=guardian.contact,
            birth=guardian.birth,
            user_id=guardian.user_id
        )
        db.add(new_guardian)
        await db.commit()
        await db.refresh(new_guardian)
        return new_guardian

    @app.get("/guardians/", response_model=list[GuardianResponse])
    async def read_guardians(db: AsyncSession = Depends(get_db)):
        result = await db.execute(select(Guardian))
        guardians = result.scalars().all()
        return guardians

else:
    # 데이터베이스 없이 실행될 때 대체 엔드포인트
    @app.get("/users/")
    async def read_users_fallback():
        return {"message": "Database not configured. Please add PostgreSQL service in Railway."}

    @app.get("/guardians/")
    async def read_guardians_fallback():
        return {"message": "Database not configured. Please add PostgreSQL service in Railway."}

# 라우터 등록 (사용 가능한 경우에만)
if routers_available:
    try:
        app.include_router(activity_router, prefix="/api", tags=["Activity Time"])
        app.include_router(heartrate_router, prefix="/api", tags=["heartrate"]) 
        app.include_router(gps_router, prefix="/api", tags=["gps"]) 
        app.include_router(obstacle_router, prefix="/api", tags=["obstacle"]) 
        app.include_router(pothole_router, prefix="/api", tags=["pothole"])
        app.include_router(accelerometer_router, prefix="/api", tags=["accelerometer"])
        app.include_router(profile_router, prefix="/api", tags=["profile"])
        app.include_router(report_router, prefix="/api", tags=["report"])
        logger.info("✅ All routers registered successfully")
    except Exception as e:
        logger.error(f"❌ Router registration failed: {e}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)