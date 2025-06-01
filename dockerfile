# Ubuntu 24.04 기반 FastAPI Walker 프로젝트 Dockerfile
FROM ubuntu:24.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 시스템 패키지 업데이트 및 필수 도구 설치
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  curl \
  git \
  # OpenGL/Computer Vision 관련 라이브러리 (Ubuntu 24.04 호환)
  libgl1-mesa-glx \
  libgl1-mesa-dri \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libgthread-2.0-0 \
  # OpenCV 의존성
  libgstreamer1.0-0 \
  libgstreamer-plugins-base1.0-0 \
  libgtk-3-0 \
  libavcodec-dev \
  libavformat-dev \
  libswscale-dev \
  # 추가 GUI 라이브러리 (headless 환경용)
  libegl1-mesa \
  libxcb1 \
  && rm -rf /var/lib/apt/lists/*

# Python 심볼릭 링크 생성 (Ubuntu 24.04에서 python -> python3)
RUN ln -s /usr/bin/python3 /usr/bin/python

# pip 업그레이드
RUN python3 -m pip install --upgrade pip

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 및 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 포트 8000 노출 (FastAPI 기본 포트)
EXPOSE 8000

# 헬스체크 추가
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# FastAPI 애플리케이션 실행
# main.py에 app 객체가 있다고 가정
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]