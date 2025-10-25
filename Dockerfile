FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y wireguard-tools iproute2 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY .env .env

RUN mkdir -p /app/data

CMD ["python", "src/main.py"]