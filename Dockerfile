FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y gcc libpq-dev dos2unix \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/static /app/staticfiles /app/mediafiles /app/logs
RUN mkdir -p /app/staticfiles/drf_spectacular_sidecar/swagger-ui-dist

RUN dos2unix entrypoint.sh && chmod +x entrypoint.sh

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]