FROM ubuntu:22.04

# 시스템 의존성 설치
RUN apt-get update && \
  apt-get install -y libgl1-mesa-glx \
  apt-get install -y libglib2.0-0 && \
  apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip3 install opencv-python-headless

CMD ["python", "main.py"]
