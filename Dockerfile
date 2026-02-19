FROM python:3.9-slim

# Install system dependencies required for dlib and opencv
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libopenblas-dev \
    liblapack-dev \
    libx11-dev \
    libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage cache
COPY requirements.txt .

# Install python dependencies
# Limit compilation parallelism to avoid OOM on free tier
ENV CMAKE_BUILD_PARALLEL_LEVEL=1
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Run the application
# Render provides PORT environment variable
CMD gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT run:app
