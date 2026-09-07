FROM python:3.13-slim AS base

WORKDIR /app

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user
RUN adduser --disabled-password --gecos "" appuser && \
    chown -R appuser:appuser /app
USER appuser
ENV PATH="/home/appuser/.local/bin:$PATH"

# Copy application
COPY src/ src/
COPY evals/ evals/

# Expose port (Cloud Run sets $PORT)
ENV PORT=8080
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start the ADK web server
CMD ["sh", "-c", "python -m uvicorn adk_cx_support_orchestrator.server:app --host 0.0.0.0 --port ${PORT}"]
