FROM ubuntu:22.04

# 시스템 패키지 설치
RUN apt-get update && \
  apt-get upgrade \
  apt-get install -y libsm6 libxext6 ffmpeg libfontconfig1 libxrender1 libgl1-mesa-glx && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Python 패키지 설치
RUN pip install --no-cache-dir --upgrade pip && \
  pip install opencv-python-headless && \
  pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision && \
  pip install ultralytics && \
  pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
