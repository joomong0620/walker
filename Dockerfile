# 베이스 이미지 선택
FROM python:3.12

# 작업 디렉토리 설정
WORKDIR /app

# 종속성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 복사
COPY . .

# 환경변수 설정 (Railway 호환)
ENV PORT=${PORT}
EXPOSE ${PORT}

# 앱 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
