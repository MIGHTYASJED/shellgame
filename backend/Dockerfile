FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
# falkordblite ships a bundled redis-server + FalkorDB module; libgomp is needed by the module.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY backend/ /app/backend/
COPY data/sample/ /app/data/sample/

EXPOSE 8000
CMD ["uvicorn", "shellgame.api:app", "--host", "0.0.0.0", "--port", "8000"]
