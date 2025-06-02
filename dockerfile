# 사용할 Python 기본 이미지를 선택합니다.
FROM python:3.12-slim

# 애플리케이션이 실행될 작업 디렉토리를 설정합니다.
WORKDIR /app

# 시스템 패키지 목록을 업데이트하고, OpenCV 실행에 필요한 라이브러리들을 설치합니다.
# '--no-install-recommends' 플래그는 불필요한 패키지 설치를 줄여줍니다.
# 'rm -rf /var/lib/apt/lists/*'는 캐시를 정리하여 이미지 크기를 줄입니다.
RUN apt-get update && \
  apt-get install -y --no-install-recommends \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 && \
  rm -rf /var/lib/apt/lists/*

# requirements.txt 파일을 먼저 복사합니다. (캐싱 효율성)
COPY requirements.txt .

# 가상 환경을 만들고 pip를 업그레이드한 후, requirements.txt의 패키지들을 설치합니다.
# requirements.txt에는 opencv-python-headless가 포함되어 있어야 합니다.
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install -r requirements.txt

# 가상 환경을 기본 Python 환경으로 설정합니다.
ENV PATH="/opt/venv/bin:$PATH"

# 나머지 애플리케이션 코드를 복사합니다.
COPY . /app

# 애플리케이션이 사용할 포트를 노출합니다. (예: FastAPI의 기본 포트 8000 또는 사용자 설정 포트 5000)
EXPOSE 5000

# 애플리케이션 실행 명령어를 지정합니다.
CMD ["python", "main.py"]
