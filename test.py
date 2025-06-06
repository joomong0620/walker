# app.py에서 데이터베이스 연결 부분 확인
# 환경 변수로 DATABASE_URL이 제대로 설정되어 있는지 확인

import os
DATABASE_URL = os.getenv("DATABASE_URL")
print(f"Database URL: {DATABASE_URL}")  # 디버깅용