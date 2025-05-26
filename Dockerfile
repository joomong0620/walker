# ✅ 슬림한 Python 베이스 이미지
FROM python:3.12-slim

# ✅ 시스템 패키지 최소 설치 (필요 시만 확장)
RUN apt-get update && apt-get install -y \
  gcc \
  libgl1-mesa-glx \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ✅ 필요 없는 파일 방지
COPY requirements.txt .

# ✅ 캐시 없이 설치
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

# ✅ 포트는 EXPOSE만 사용 (Railway 자동 인식)
EXPOSE 8000

# ✅ 실행 커맨드
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
