FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire repo (we need connectors/data)
COPY . .

# Set working directory to backend
WORKDIR /app/backend

# Railway sets PORT dynamically
ENV PORT=8000

# Run uvicorn with dynamic port
CMD python -m uvicorn main:app --host 0.0.0.0 --port $PORT
