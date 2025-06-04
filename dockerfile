FROM python:3.10-slim

# 시스템 의존성 설치
RUN apt-get update && \
  apt-get install -y libgl1-mesa-glx libglib2.0-0 && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python", "main.py"]
