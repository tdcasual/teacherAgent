FROM python:3.13-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

COPY services/api/requirements.txt /app/requirements.txt
ENV PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy only what the API needs (keeps image smaller and builds faster).
COPY services /app/services
COPY skills /app/skills
COPY config /app/config
COPY scripts /app/scripts
COPY prompts /app/prompts
COPY llm_gateway.py /app/llm_gateway.py
COPY mem0_config.py /app/mem0_config.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DATA_DIR=/app/data
ENV UPLOADS_DIR=/app/uploads

EXPOSE 8000
CMD ["uvicorn", "services.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
