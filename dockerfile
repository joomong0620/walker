FROM ubuntu:22.04

# 시스템 패키지 설치
RUN apt-get update && \
  apt-get install -y libgl1-mesa-glx libglib2.0-0 python3-pip && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Python 패키지 설치 (순서 중요!)
RUN pip3 install --no-cache-dir --upgrade pip && \
  pip3 install opencv-python-headless && \
  pip3 install --index-url https://download.pytorch.org/whl/cpu torch torchvision && \
  pip3 install ultralytics && \
  pip3 uninstall -y opencv-python

RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
