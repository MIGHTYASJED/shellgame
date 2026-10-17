# Hugging Face Space (Docker SDK): builds the backend straight from the GitHub repo.
# Bump CACHEBUST (or use "Factory rebuild") to pull the latest commit.
FROM python:3.13-slim
ARG CACHEBUST=1
RUN apt-get update && apt-get install -y --no-install-recommends git libgomp1 && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 https://github.com/MIGHTYASJED/shellgame /src && \
    mkdir -p /app && cp -r /src/backend /src/data /app/ && rm -rf /src
WORKDIR /app/backend
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED=1 FALKORDB_LITE_PATH=/tmp/shellgame/real.db PORT=7860
EXPOSE 7860
CMD mkdir -p /tmp/shellgame && cp /app/data/real.db "$FALKORDB_LITE_PATH" && \
    uvicorn shellgame.api:app --host 0.0.0.0 --port "$PORT"
