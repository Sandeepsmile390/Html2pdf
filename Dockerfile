# Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000

# Install Chromium and necessary fonts to render text/emojis correctly in PDF prints
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    fonts-dejavu \
    fontconfig \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy requirements and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download static Tailwind CSS to avoid runtime JIT compilation overhead and timeouts
RUN mkdir -p /app/static && \
    apt-get update && apt-get install -y --no-install-recommends wget && \
    wget -O /app/static/tailwind.min.css https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css && \
    apt-get purge -y --auto-remove wget && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the application files
COPY app.py /app/
COPY templates/ /app/templates/

# Expose the production port
EXPOSE 5000

# Run the gunicorn production WSGI server with an extended timeout to allow Chromium rendering time
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--timeout", "120", "app:app"]
