# Use Python 3.13 slim as base image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install pip dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy app files
COPY . .

# Expose the port Flask runs on
# EXPOSE 5000

# Run the app from src folder
CMD ["python", "src/app.py"]