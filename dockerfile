# Ubuntu 이미지를 기반으로 합니다.
FROM ubuntu:22.04

# 필요한 패키지들을 설치합니다.
# python3.12, pip, virtualenv, OpenCV 관련 라이브러리 등을 포함합니다.
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  python3.12 \
  python3.12-dev \
  python3-pip \
  virtualenv \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 \
  mesa-dri-common \
  libfontconfig1 \
  libfreetype6 \
  libxrandr2 \
  libxi6 \
  libjpeg-dev \
  libpng-dev \
  libtiff-dev \
  && \
  rm -rf /var/lib/apt/lists/*

# Python 가상 환경을 설정합니다.
RUN virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Python 패키지들을 설치합니다.
WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 애플리케이션 코드를 복사합니다.
COPY . /app

# 사용할 포트를 노출합니다.
EXPOSE 8000

# 실행 명령어를 설정합니다.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
