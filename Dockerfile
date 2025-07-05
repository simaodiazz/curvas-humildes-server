FROM python:3.11-slim

LABEL org.opencontainers.image.title="Curvas Sistema"
LABEL org.opencontainers.image.description="Dockerfile for Flask + Gunicorn + SSH"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="https://github.com/simaodiazz"
LABEL org.opencontainers.image.url="https://github.com/simaodiazz/projeto"
LABEL org.opencontainers.image.source="https://github.com/simaodiazz/projeto"

WORKDIR /app

COPY . .

RUN apt-get update \
 && apt-get install -y gcc python3-dev musl-dev openssh-server \
 && rm -rf /var/lib/apt/lists/*

RUN pip install -r requirements.txt

RUN useradd -m -d /home/admin admin && \
    mkdir -p /home/admin/.ssh && \
    chown -R admin:admin /home/admin/.ssh && \
    chmod 700 /home/admin/.ssh

RUN echo 'admin:admin' | chpasswd

ARG ADMIN_SSH_PUB
ENV ADMIN_SSH_PUB=${ADMIN_SSH_PUB:-}

RUN if [ -n "${ADMIN_SSH_PUB}" ]; then \
      echo "${ADMIN_SSH_PUB}" > /home/admin/.ssh/authorized_keys && \
      chmod 600 /home/admin/.ssh/authorized_keys && \
      chown admin:admin /home/admin/.ssh/authorized_keys; \
    fi

RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

EXPOSE 5000 22

RUN mkdir -p /var/run/sshd

# ENTRYPOINT
# Inicia ambos: SSH e Gunicorn
CMD service ssh start && \
    gunicorn -w 3 -b 0.0.0.0:5000 "app:create_app(config_object_name='config')"
