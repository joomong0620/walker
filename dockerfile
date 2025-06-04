FROM ubuntu:22.04

# apt 업데이트 및 필요한 라이브러리 설치를 하나의 RUN 명령어로 처리합니다.
# --no-install-recommends 옵션은 권장 패키지 설치를 막아 이미지 크기를 줄여줍니다.
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  python3.12 \
  python3.12-dev \
  python3-pip \
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
  ffmpeg && \
  # 설치 후 apt 캐시를 정리하여 이미지 크기를 더욱 줄입니다.
  rm -rf /var/lib/apt/lists/*

# 기본 python 명령어가 python3.12를 가리키도록 설정합니다.
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

# 애플리케이션 코드를 위한 작업 디렉토리를 설정합니다.
WORKDIR /app

# requirements.txt 파일을 복사하고 Python 의존성을 설치합니다.
COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

# 나머지 애플리케이션 코드를 복사합니다.
COPY . .

# 애플리케이션이 사용할 포트를 노출합니다.
EXPOSE 8000

# 컨테이너 실행 시 실행될 명령어입니다.
# uvicorn은 PORT 환경 변수를 직접 사용 가능하여 sh -c 없이도 작동합니다.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "${PORT:-8000}"]
