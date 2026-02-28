FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for native extensions (numpy, sentence-transformers)
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*

# Create data directories
RUN mkdir -p /app/data /app/garden_graph/data

# Copy requirements first for caching
COPY requirements.txt .
COPY garden_graph/requirements.txt garden_graph/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port (matches default in server.py)
EXPOSE 5050

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5050/health')" || exit 1

# Run the server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "5050"]
