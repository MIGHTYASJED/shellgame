# Backend image. Build from the repo root:  docker build -f backend/Dockerfile -t shellgame-api .
# Runs FastAPI + embedded FalkorDB (falkordblite bundles redis-server with the FalkorDB module)
# preloaded with the real ICIJ/OpenSanctions graph in data/real.db.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    FALKORDB_LITE_PATH=/tmp/shellgame/real.db PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .
COPY data/real.db /app/data/real.db

EXPOSE 8000
# Copy the graph to a writable path (case memory is written next to it), then serve.
CMD mkdir -p /tmp/shellgame && cp /app/data/real.db "$FALKORDB_LITE_PATH" && \
    uvicorn shellgame.api:app --host 0.0.0.0 --port "$PORT"
