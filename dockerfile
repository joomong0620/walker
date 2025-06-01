FROM python:3.12

RUN apt-get update && \
  apt-get install -y freetds-dev libssl-dev && \
  rm -rf /var/lib/apt/lists/*

ENV LDFLAGS="-L/usr/lib/x86_64-linux-gnu -L/usr/lib/i386-linux-gnu"
ENV CFLAGS="-I/usr/include"

WORKDIR /app
COPY requirements.txt .
COPY . .

RUN apt-get update && \
  apt-get install -y freetds-dev libssl-dev && \
  rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]