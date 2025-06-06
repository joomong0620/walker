FROM ubuntu:22.04

# 시스템 패키지 설치 (OpenCV headless + 필수 라이브러리)
RUN apt-get update && \
  apt-get install -y \
  python3 \
  python3-pip \
  python3-dev \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libgcc-s1 \
  build-essential \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Python 심볼릭 링크 설정
RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# requirements.txt 먼저 복사 (Docker 캐시 최적화)
COPY requirements.txt .

# pip 업그레이드 및 패키지 설치
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt

# 나머지 애플리케이션 파일 복사
COPY . .

# 환경 변수 설정
ENV OPENCV_IO_ENABLE_OPENEXR=0
ENV QT_QPA_PLATFORM=offscreen
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 포트 노출
EXPOSE 8000

# FastAPI 앱 실행 (uvicorn 사용)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]