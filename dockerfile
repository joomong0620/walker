FROM ubuntu:24.04

# 필요한 패키지 설치
RUN apt-get update && apt-get install -y \
  libgl1-mesa-dev \
  libglu1-mesa-dev \
  python3 \
  python3-pip \
  && rm -rf /var/lib/apt/lists/*

# 프로젝트 파일 복사
COPY . /app
WORKDIR /app

# 의존성 설치
RUN pip3 install -r requirements.txt

# Railway에서 자동으로 PORT 환경변수 제공
EXPOSE $PORT

# FastAPI 실행
CMD ["python3", "main.py"]