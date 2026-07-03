# DocDrift backend — production container
FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; add build-essential only if a wheel needs compiling.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud platforms inject $PORT; default to 8001 locally.
ENV PORT=8001
EXPOSE 8001

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
