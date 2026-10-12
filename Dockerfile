# Finviz MCP Server Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/ ./src/
COPY pyproject.toml README.md ./
COPY run_server.py .

# Install the package
RUN pip install --no-cache-dir .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO
ENV RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Expose port for SSE transport
EXPOSE 8000

# Default command - use the installed entry point
CMD ["python", "-m", "src.oauth_server"]
