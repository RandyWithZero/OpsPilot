FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HTTP_ADDR=0.0.0.0:8080

WORKDIR /app

RUN python -m pip install --no-cache-dir boto3 pymysql

COPY services/foundation-service/ /app/

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=5s --retries=12 CMD python -m opspilot_foundation.readiness_check

CMD ["python", "-m", "opspilot_foundation.server"]
