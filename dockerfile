# Railway용 Ubuntu 24.04 기반 FastAPI Dockerfile
FROM ubuntu:24.04

# 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 시스템 패키지 설치 (libgl1 포함)
RUN apt-get update && apt-get install -y \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender-dev \
  libgomp1 \
  && rm -rf /var/lib/apt/lists/*

# Alpine 기반이라면
RUN apk add --no-cache mesa-gl glib libsm libxext libxrender

RUN apt-get update && apt-get install -y libegl1
# Python 심볼릭 링크
RUN ln -s /usr/bin/python3 /usr/bin/python

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Railway 포트 환경변수 사용
EXPOSE $PORT

# Railway용 시작 명령
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "$PORT"]
