FROM ubuntu:22.04

RUN apt-get update && \
  apt-get install -y python3-pip libgl1-mesa-glx && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 강제 제거 + 설치 확인 추가
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt && \
  pip uninstall -y opencv-python || true && \
  pip freeze | grep opencv

CMD ["python3", "main.py"]
