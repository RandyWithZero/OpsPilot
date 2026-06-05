FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV OPSPILOT_FOUNDATION_URL=http://foundation:8080

WORKDIR /app

COPY services/agent-worker/ /app/

CMD ["python", "-m", "opspilot_agent_worker"]
