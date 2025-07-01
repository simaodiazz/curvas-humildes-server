FROM python:3.11-slim

LABEL org.opencontainers.image.title="Curvas Sistema"
LABEL org.opencontainers.image.description="Dockerfile for Flask + Gunicorn"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="https://github.com/simaodiazz"
LABEL org.opencontainers.image.url="https://github.com/simaodiazz/projeto"
LABEL org.opencontainers.image.source="https://github.com/simaodiazz/projeto"

WORKDIR /app

COPY . .

# Linux dependencies
RUN apt-get update 
RUN apt-get install -y gcc python3-dev musl-dev 
RUN rm -rf /var/lib/apt/lists/*

# Install the dependencies
RUN pip install -r requirements.txt

EXPOSE 5000

HEALTHCHECK NONE

ENTRYPOINT ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "app:create_app(config_object_name=\"config\")"]
