FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 설치 (opencv 등을 위한 라이브러리 추가)
RUN apt-get update && apt-get install -y \
  gcc \
  g++ \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libglib2.0-0 \
  && rm -rf /var/lib/apt/lists/*

# requirements 먼저 복사해서 캐싱 활용
COPY requirements.txt .

# pip 업그레이드 및 패키지 설치
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 포트 설정
EXPOSE 8000

# 시작 명령어
CMD ["python", "main.py"]