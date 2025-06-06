import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
load_dotenv()  # ✅ .env 파일에서 DATABASE_URL 읽어오기

DATABASE_URL = os.getenv("DATABASE_URL")
# 비동기 엔진 생성
engine = create_async_engine(DATABASE_URL, echo=True)

# 세션 생성
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)
# FastAPI에서 사용할 세션 생성 함수
async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
        
# 데이터베이스 초기화 함수 (테이블 생성용)
async def init_db():
    async with engine.begin() as conn:
        # 여기에 초기 테이블 생성 코드 작성
        pass
