FROM python:3.11-slim

# Avoid generation of .pyc files and enable stdout/stderr buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8081

WORKDIR /app

# Install curl (required for ECS health checks)
RUN apt-get update && apt-get install -y curl

# Install pip dependencies first (cacheable layer)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose configured port
EXPOSE 8081

# Run the app as a module (the app listens on 0.0.0.0 when run this way)
CMD ["python", "-m", "src.app"]

