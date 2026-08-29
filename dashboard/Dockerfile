FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements-dashboard.txt /app/requirements-dashboard.txt
RUN python -m pip install --no-cache-dir -r /app/requirements-dashboard.txt
COPY dashboard /app/dashboard

EXPOSE 8000
ENTRYPOINT ["/app/dashboard/entrypoint.sh"]
