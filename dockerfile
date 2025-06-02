# ✅ 1. Python 기반 슬림 이미지 사용
FROM python:3.12-slim

# ✅ 2. 작업 디렉토리 설정
WORKDIR /app

# ✅ 3. 시스템 패키지 설치 (OpenCV 실행에 필요한 의존성 포함)
RUN apt-get update && apt-get install -y --no-install-recommends \
  libgl1-mesa-glx \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 \
  && rm -rf /var/lib/apt/lists/*

# ✅ 4. requirements.txt 먼저 복사 → 캐싱 최적화
COPY requirements.txt .

# ✅ 5. 가상환경 생성 및 패키지 설치
RUN python -m venv /opt/venv && \
  . /opt/venv/bin/activate && \
  pip install --upgrade pip && \
  pip install --no-cache-dir -r requirements.txt

# ✅ 6. 환경변수 설정 (가상환경을 기본 PATH로)
ENV PATH="/opt/venv/bin:$PATH"

# ✅ 7. 앱 코드 복사
COPY . /app

# ✅ 8. 포트 노출 (FastAPI 기본 포트 또는 사용자 지정)
EXPOSE 5000

# ✅ 9. 애플리케이션 실행
CMD ["python", "main.py"]
