FROM ubuntu:22.04

# 시스템 패키지 설치
RUN apt-get update && \
  apt-get install -y python3-pip libgl1 && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Python 패키지 설치 + opencv-python 제거
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt && \
  pip uninstall -y opencv-python || true

CMD ["python3", "main.py"]
