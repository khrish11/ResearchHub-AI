# Use official Python lightweight image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV="production"

# Install system dependencies (build-essential for some pip packages if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Ensure ASGI servers are installed
RUN pip install --no-cache-dir "uvicorn[standard]" gunicorn

# Copy application files
COPY . .

# Expose port (Internal to container, map on deployment)
EXPOSE 8080

# Run gunicorn with uvicorn workers
# -w 4: 4 worker processes for concurrency
# -k uvicorn.workers.UvicornWorker: async worker class
# -b 0.0.0.0:8080: bind to all interfaces on port 8080
CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8080"]
