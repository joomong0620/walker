# 사용할 Python 기본 이미지를 선택합니다. (slim 버전)
FROM python:3.12-slim

# 애플리케이션이 실행될 작업 디렉토리를 설정합니다.
WORKDIR /app

# 시스템 패키지 목록을 업데이트합니다.
RUN apt-get update

# OpenCV 실행에 필요한 라이브러리들을 설치합니다.
# libGL.so.1 오류 해결 및 관련 의존성 충족을 위한 패키지 목록입니다.
# 이전에 포함했던 패키지들과 추가적인 의존성들을 포함시켰습니다.
RUN apt-get install -y --no-install-recommends \
  libgl1 \
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
  # 설치 후 apt 캐시 및 불필요한 파일들을 정리하여 이미지 크기를 최적화합니다.
  rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# requirements.txt 파일을 먼저 복사합니다. (Docker 빌드 시 캐싱 효율성 증대)
COPY requirements.txt .

# 가상 환경을 만들고 pip를 최신 버전으로 업그레이드한 후, requirements.txt의 패키지들을 설치합니다.
# requirements.txt에는 opencv-python-headless 또는 opencv-python이 포함되어 있어야 합니다.
# headless 버전 사용을 권장합니다.
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install -r requirements.txt

# 가상 환경을 컨테이너의 기본 Python 환경으로 설정합니다.
ENV PATH="/opt/venv/bin:$PATH"

# 나머지 애플리케이션 코드를 작업 디렉토리로 복사합니다.
COPY . /app

# 애플리케이션이 사용할 포트를 노출합니다. (정보 제공 목적)
# EXPOSE 5000 # 혹시 5000 포트를 사용하신다면 이걸 사용하시고 CMD도 맞춰주세요.
EXPOSE 8000 

# 컨테이너 시작 시 실행될 명령어를 지정합니다.
# FastAPI 애플리케이션을 Uvicorn으로 실행하고, Railway가 제공하는 PORT 환경 변수를 사용하도록 설정합니다.
# 'main:app' 부분은 실제 FastAPI 애플리케이션 인스턴스의 위치와 변수 이름에 맞게 수정해주세요.
# 예: 프로젝트 최상위에 main.py 파일이 있고 그 안에 'app = FastAPI()'가 있다면 'main:app' 입니다.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
