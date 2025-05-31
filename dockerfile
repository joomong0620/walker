# 베이스 이미지: Python 3.12 slim 버전 사용
FROM python:3.12-slim

# 필수 패키지 설치 (cv2 실행에 필요한 라이브러리 포함)
RUN apt-get update && apt-get install -y \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  ffmpeg \
  && rm -rf /var/lib/apt/lists/*

# OpenCV 설치
RUN pip install --no-cache-dir opencv-python

# 작업 디렉토리 설정
WORKDIR /app

# requirements.txt 복사 후 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 프로젝트 전체 복사
COPY . .

# 컨테이너 시작 시 실행할 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
