# Medicare Helper: one container = FastAPI API + the built React site.
# Stage 1: build the web app
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app/src PYTHONUNBUFFERED=1 TRACE_LOG=0
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY --from=web /web/dist ./web/dist
# data/releases is a volume: downloaded from the GitHub data release at startup and refreshed while running
RUN mkdir -p data/releases data/processed uploads logs
EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
