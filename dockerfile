# Railway용 Ubuntu 기반 FastAPI Dockerfile
FROM ubuntu:22.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 시스템 패키지 설치 (libgl1-mesa-glx 포함)
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  python3-dev \
  build-essential \
  curl \
  # OpenGL 라이브러리 설치
  libgl1-mesa-glx \
  libgl1-mesa-dri \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  && rm -rf /var/lib/apt/lists/*

# Python 심볼릭 링크
RUN ln -s /usr/bin/python3 /usr/bin/python

# 작업 디렉토리
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Railway 포트 환경변수 사용
EXPOSE $PORT

# Railway용 시작 명령
CMD uvicorn main:app --host 0.0.0.0 --port $PORT