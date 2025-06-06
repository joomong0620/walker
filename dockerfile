FROM ubuntu:22.04

# 시스템 패키지 설치
RUN apt-get update && \
  apt-get install -y python3-pip libgl1-mesa-glx && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# 수동 설치: requirements.txt 무시하고 opencv-python 제거
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir opencv-python-headless==4.8.1.78 && \
  pip install --no-cache-dir ultralytics[core]==8.3.99 --no-deps && \
  pip install --no-cache-dir \
  fastapi uvicorn pandas torch torchvision seaborn SQLAlchemy \
  matplotlib scikit-learn python-dotenv python-multipart psycopg2-binary && \
  pip uninstall -y opencv-python || true && \
  pip freeze | grep opencv

CMD ["python3", "main.py"]
