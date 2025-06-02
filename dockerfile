FROM ubuntu:22.04

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
  libtiff-dev && \
  rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python python /usr/bin/python3.12 1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
