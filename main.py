from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import update, delete
from pydantic import BaseModel
from model.models import Base, User, Guardian
from utils import sqlalchemy_to_dict
from routers.activity import router as activity_router
from routers.heartrate import router as heartrate_router
from routers.gps import router as gps_router
from fastapi.middleware.cors import CORSMiddleware
# from io import BytesIO
# from PIL import Image
# from ai import predict_image  # YOLO 함수 불러오기

# PostgreSQL 연결 설정
DATABASE_URL = "postgresql+asyncpg://postgres:1514@localhost/walker"  # 사용자 정보 수정 필요

# SQLAlchemy 비동기 엔진 및 세션 설정
engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# FastAPI 애플리케이션 생성
app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # 허용할 프론트엔드 도메인
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 HTTP 헤더 허용
)

# 의존성: 데이터베이스 세션
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

# Pydantic 모델 정의
class UserCreate(BaseModel):
    user_id: str
    name: str
    contact: str
    birth: str

    class Config:
        orm_mode = True

class UserResponse(BaseModel):
    user_id: str
    name: str
    contact: str
    birth: str

    class Config:
        orm_mode = True

# 애플리케이션 시작 시 데이터베이스 초기화
@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# 사용자 추가
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    # 중복 검사
    existing_user = await db.execute(select(User).where(User.user_id == user.user_id))
    if existing_user.scalar():
        raise HTTPException(status_code=400, detail="User already exists")

    # 사용자 추가
    new_user = User(user_id=user.user_id, name=user.name, contact=user.contact, birth=user.birth)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

# 모든 사용자 조회
@app.get("/users/", response_model=list[UserResponse])
async def read_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

# 특정 사용자 조회
@app.get("/users/{user_id}", response_model=UserResponse)
async def read_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

# 사용자 정보 수정
@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: str, user: UserCreate, db: AsyncSession = Depends(get_db)):
    # 사용자 존재 여부 확인
    result = await db.execute(select(User).where(User.user_id == user_id))
    existing_user = result.scalar()
    if not existing_user:
        raise HTTPException(status_code=404, detail="User not found")

    # 사용자 정보 수정
    await db.execute(
        update(User)
        .where(User.user_id == user_id)
        .values(name=user.name, contact=user.contact, birth=user.birth)
    )
    await db.commit()

    # 수정된 사용자 반환
    updated_user = await db.execute(select(User).where(User.user_id == user_id))
    return updated_user.scalar()

# 사용자 삭제
@app.delete("/users/{user_id}", response_model=dict)
async def delete_user(user_id: str, db: AsyncSession = Depends(get_db)):
    # 사용자 존재 여부 확인
    result = await db.execute(select(User).where(User.user_id == user_id))
    user = result.scalar()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 사용자 삭제
    await db.execute(delete(User).where(User.user_id == user_id))
    await db.commit()
    return {"message": f"User {user_id} deleted successfully"}
# Pydantic 모델 정의
class GuardianCreate(BaseModel):
    guardian_id: str
    name: str
    contact: str
    birth: str
    user_id: str  # ✅ 보호자가 연결될 사용자 ID

    class Config:
        orm_mode = True

class GuardianResponse(BaseModel):
    guardian_id: str
    name: str
    contact: str
    birth: str
    user_id: str

    class Config:
        orm_mode = True

# 보호자 추가
@app.post("/guardians/", response_model=GuardianResponse)
async def create_guardian(guardian: GuardianCreate, db: AsyncSession = Depends(get_db)):
    # 중복 검사
    existing_guardian = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian.guardian_id))
    if existing_guardian.scalar():
        raise HTTPException(status_code=400, detail="Guardian already exists")

    # 보호자 추가
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

# 모든 보호자 조회
@app.get("/guardians/", response_model=list[GuardianResponse])
async def read_guardians(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Guardian))
    guardians = result.scalars().all()
    return guardians

# 특정 보호자 조회
@app.get("/guardians/{guardian_id}", response_model=GuardianResponse)
async def read_guardian(guardian_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian_id))
    guardian = result.scalar()
    if not guardian:
        raise HTTPException(status_code=404, detail="Guardian not found")
    return guardian

# 특정 사용자(user_id)에 연결된 보호자 조회
@app.get("/users/{user_id}/guardians", response_model=list[GuardianResponse])
async def read_guardians_by_user(user_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Guardian).where(Guardian.user_id == user_id))
    guardians = result.scalars().all()
    return guardians

# 보호자 정보 수정
@app.put("/guardians/{guardian_id}", response_model=GuardianResponse)
async def update_guardian(guardian_id: str, guardian: GuardianCreate, db: AsyncSession = Depends(get_db)):
    # 보호자 존재 여부 확인
    result = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian_id))
    existing_guardian = result.scalar()
    if not existing_guardian:
        raise HTTPException(status_code=404, detail="Guardian not found")

    # 보호자 정보 수정
    await db.execute(
        update(Guardian)
        .where(Guardian.guardian_id == guardian_id)
        .values(name=guardian.name, contact=guardian.contact, birth=guardian.birth, user_id=guardian.user_id)
    )
    await db.commit()

    # 수정된 보호자 반환
    updated_guardian = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian_id))
    return updated_guardian.scalar()

# 보호자 삭제
@app.delete("/guardians/{guardian_id}", response_model=dict)
async def delete_guardian(guardian_id: str, db: AsyncSession = Depends(get_db)):
    # 보호자 존재 여부 확인
    result = await db.execute(select(Guardian).where(Guardian.guardian_id == guardian_id))
    guardian = result.scalar()
    if not guardian:
        raise HTTPException(status_code=404, detail="Guardian not found")

    # 보호자 삭제
    await db.execute(delete(Guardian).where(Guardian.guardian_id == guardian_id))
    await db.commit()
    return {"message": f"Guardian {guardian_id} deleted successfully"}




# 라우터 등록
app.include_router(activity_router, prefix="/api", tags=["Activity Time"])
app.include_router(heartrate_router, prefix="/api", tags=["heartrate"]) 
app.include_router(gps_router, prefix="/api", tags=["gps"]) 