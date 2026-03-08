FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better caching
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the actual code (backend/ and redis/ must be mapped or copied)
COPY backend/ backend/
COPY redis/ redis/

WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
