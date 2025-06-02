# Ubuntu 22.04 기반 이미지
FROM ubuntu:22.04

# 필수 패키지 설치 (OpenCV 관련 포함)
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  python3.12 \
  python3.12-dev \
  python3-pip \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 \
  mesa-dri-common \
  libfontconfig1 \
  libfreetype6 \
  libxrandr2 \
  libxi6 \
  libjpeg-dev \
  libpng-dev \
  libtiff-dev \
  && \
  rm -rf /var/lib/apt/lists/*

# python3.12을 기본 python으로 설정 (필수!)
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# 작업 디렉토리 설정
WORKDIR /app

# requirements 복사 및 설치
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

# 앱 코드 복사
COPY . .

# 포트 오픈
EXPOSE 8000

# 실행 명령어 설정 (환경변수 PORT 없으면 8000)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
