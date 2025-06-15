# Stage 1: Build dependencies
FROM python:3.10-alpine as builder

WORKDIR /app

# Install minimal system dependencies
RUN apk add --no-cache \
    build-base \
    libglib2 \
    libxrender \
    libxext

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --compile --no-binary :all: -r requirements.txt

# Stage 2: Final image
FROM python:3.10-alpine

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages/ /usr/local/lib/python3.10/site-packages/
COPY --from=builder /usr/local/bin/ /usr/local/bin/
COPY --from=builder /usr/local/lib/ /usr/local/lib/

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Expose port and start command
EXPOSE 5000
ENTRYPOINT ["gunicorn"]
CMD ["--bind", "0.0.0.0:5000", "app:app"]

# Expose port
EXPOSE 5000

# Start application
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
