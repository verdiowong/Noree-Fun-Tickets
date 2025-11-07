FROM python:3.12-slim

# Set working directory
WORKDIR /usr/src/app

# Install curl (required for ECS health checks)
RUN apt-get update && apt-get install -y curl

# Copy and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/app.py .

# Expose the port Flask runs on
EXPOSE 8084

# Run your app
CMD ["python", "./app.py"]
