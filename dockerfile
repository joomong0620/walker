# Python 3.12 슬림 이미지 사용
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 업데이트 및 OpenCV 의존성 설치
RUN apt-get update && apt-get install -y \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  libgthread-2.0-0 \
  libglib2.0-dev \
  pkg-config \
  gcc \
  g++ \
  && rm -rf /var/lib/apt/lists/*

# Python 의존성 파일 복사
COPY requirements.txt .

# Python 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# boot.sh 스크립트에 실행 권한 부여
RUN chmod +x boot.sh

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1
ENV QT_QPA_PLATFORM=offscreen
ENV OPENCV_IO_ENABLE_OPENEXR=1

# 포트 노출
EXPOSE 8000

# 애플리케이션 시작
CMD ["./boot.sh", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]