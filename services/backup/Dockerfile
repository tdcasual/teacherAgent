FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash \
       ca-certificates \
       curl \
       tar \
       gzip \
       unzip \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir awscli

# Install ossutil v2 (linux amd64)
RUN curl -fsSL -o /tmp/ossutil.zip https://gosspublic.alicdn.com/ossutil/v2/2.0.4/ossutil-2.0.4-linux-amd64.zip \
    && unzip /tmp/ossutil.zip -d /tmp \
    && mv /tmp/ossutil-2.0.4-linux-amd64/ossutil /usr/local/bin/ossutil \
    && chmod +x /usr/local/bin/ossutil \
    && rm -rf /tmp/ossutil.zip /tmp/ossutil-2.0.4-linux-amd64

WORKDIR /workspace
