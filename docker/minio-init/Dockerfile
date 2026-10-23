FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
RUN pip install --no-cache-dir boto3==1.38.22
COPY init_minio.py /app/init_minio.py
ENTRYPOINT ["python", "/app/init_minio.py"]
