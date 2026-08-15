FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Expose ports for API (8000) and Streamlit Dashboard (8501)
EXPOSE 8000
EXPOSE 8501

# Default command runs checks, then starts services (or overridden in compose)
CMD ["python", "run.py"]
