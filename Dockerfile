# ─── Stage 1: Build Frontend ──────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ─── Stage 2: Final Python Image ──────────────────────────────────
FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
# git is required by CodeBuild during CI/CD pull steps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY . .

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist /workspace/frontend/dist

# Port used by uvicorn — ALB forwards traffic here
EXPOSE 8000

# ECS health check — polls /api/health every 30s
# Container is marked unhealthy (and replaced) after 3 consecutive failures
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start the app
CMD ["python", "run.py"]
