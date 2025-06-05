FROM ubuntu:22.04

# 시스템 패키지 설치
RUN apt-get update && \
  apt-get upgrade -y && \
  apt-get install -y libgl1 libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리 설정
WORKDIR /app
COPY . .

# Python 패키지 설치
RUN apt-get install -y python3-pip && \
  pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
