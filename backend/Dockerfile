FROM python:3.13-slim

# System deps for xgboost, numpy, and general build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and config
COPY src/ ./src/
COPY config/ ./config/

# Create ML data directories (will be volume-mounted)
RUN mkdir -p src/ml/data src/ml/models

# Default: run the bot logic
ENV PYTHONUNBUFFERED=1
ENV PYTHONUTF8=1

CMD ["python", "src/main.py"]
