import os
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

async def test_connection():
    if not DATABASE_URL:
        print("❌ DATABASE_URL 환경 변수를 찾을 수 없습니다.")
        return

    print("데이터베이스 연결을 시도 중입니다...")
    try:
        engine = create_async_engine(DATABASE_URL, echo=True)
        async with engine.connect() as conn:
            print("✅ 데이터베이스에 성공적으로 연결되었습니다!")
        await engine.dispose()
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        print("연결 URL, 비밀번호, 호스트, 포트 등을 다시 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(test_connection())