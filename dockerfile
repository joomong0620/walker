FROM ubuntu:22.04

# 시스템 패키지 설치 (libgl1 명확히!)
RUN apt-get update && \
  apt-get install -y python3-pip libgl1 && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리
WORKDIR /app
COPY . .

# Python 패키지 설치
RUN pip install --no-cache-dir --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]
