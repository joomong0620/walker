FROM ubuntu:24.04

# 필요한 패키지 설치 (OpenCV와 GUI 관련 라이브러리들)
RUN apt-get update && apt-get install -y \
  python3 \
  python3-pip \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libgthread-2.0-0 \
  libgtk-3-0 \
  libavcodec-dev \
  libavformat-dev \
  libswscale-dev \
  libv4l-dev \
  libxvidcore-dev \
  libx264-dev \
  libjpeg-dev \
  libpng-dev \
  libtiff-dev \
  libatlas-base-dev \
  gfortran \
  wget \
  && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 먼저 복사 (Docker 캐싱 최적화)
COPY requirements.txt .

# OpenCV headless 버전 설치 (GUI 없는 서버 환경용)
RUN pip3 install --no-cache-dir opencv-python-headless

# 나머지 의존성 설치
RUN pip3 install --no-cache-dir -r requirements.txt

# 프로젝트 파일 복사
COPY . .

# Railway에서 자동으로 PORT 환경변수 제공
EXPOSE $PORT

# 환경변수 설정 (headless 모드)
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=offscreen

# FastAPI 실행
CMD ["python3", "main.py"]