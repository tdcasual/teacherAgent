FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY services/mcp/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy only what the MCP server needs.
COPY services /app/services
COPY skills /app/skills
COPY scripts /app/scripts
COPY config /app/config
COPY llm_gateway.py /app/llm_gateway.py
COPY mem0_config.py /app/mem0_config.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DATA_DIR=/app/data

RUN adduser --disabled-password --no-create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
USER appuser

EXPOSE 9000
CMD ["uvicorn", "services.mcp.app:app", "--host", "0.0.0.0", "--port", "9000"]
