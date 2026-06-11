FROM python:3.11-slim

# Install basic compile utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python dependencies list and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all backend files (which now includes the static frontend assets)
COPY backend/ .

# Create the local upload directory and ensure global read-write permissions
# Hugging Face runs containers with non-root user (UID 1000), so we chmod 777 /app
RUN mkdir -p /app/storage/resumes && chmod -R 777 /app

# Hugging Face Spaces expects the container to run on port 7860
EXPOSE 7860

# Run the backend FastAPI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
