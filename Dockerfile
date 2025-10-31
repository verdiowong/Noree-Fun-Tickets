FROM python:3.11-slim

# Avoid generation of .pyc files and enable stdout/stderr buffering
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001

WORKDIR /app

# Install pip dependencies first (cacheable layer)
COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose configured port
EXPOSE 5001

# Run the app as a module (the app listens on 0.0.0.0 when run this way)
CMD ["python", "-m", "src.app"]

