# Use an official lightweight Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5000 \
    DBUS_SESSION_BUS_ADDRESS=disabled: \
    HOME=/tmp

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

# Pre-download static Tailwind CSS and handwriting Google Fonts to avoid runtime network dependencies, timeouts, and rendering failures
RUN mkdir -p /app/static /usr/share/fonts/truetype/google-fonts && \
    apt-get update && apt-get install -y --no-install-recommends wget unzip && \
    wget -q -O /app/static/tailwind.min.css https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css && \
    wget -q -O /tmp/kalam.zip "https://fonts.google.com/download?family=Kalam" && \
    unzip -o /tmp/kalam.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/caveat.zip "https://fonts.google.com/download?family=Caveat" && \
    unzip -o /tmp/caveat.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/indieflower.zip "https://fonts.google.com/download?family=Indie+Flower" && \
    unzip -o /tmp/indieflower.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/architects.zip "https://fonts.google.com/download?family=Architects+Daughter" && \
    unzip -o /tmp/architects.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/patrick.zip "https://fonts.google.com/download?family=Patrick+Hand" && \
    unzip -o /tmp/patrick.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/gochihand.zip "https://fonts.google.com/download?family=Gochi+Hand" && \
    unzip -o /tmp/gochihand.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/shadows.zip "https://fonts.google.com/download?family=Shadows+Into+Light" && \
    unzip -o /tmp/shadows.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/justme.zip "https://fonts.google.com/download?family=Just+Me+Again+Down+Here" && \
    unzip -o /tmp/justme.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/covered.zip "https://fonts.google.com/download?family=Covered+By+Your+Grace" && \
    unzip -o /tmp/covered.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    wget -q -O /tmp/gloria.zip "https://fonts.google.com/download?family=Gloria+Hallelujah" && \
    unzip -o /tmp/gloria.zip -d /usr/share/fonts/truetype/google-fonts/ && \
    rm -rf /tmp/*.zip && \
    fc-cache -fv && \
    apt-get purge -y --auto-remove wget unzip && \
    rm -rf /var/lib/apt/lists/*

# Copy the rest of the application files
COPY app.py /app/
COPY templates/ /app/templates/

# Expose the production port
EXPOSE 5000

# Run the gunicorn production WSGI server with a single worker process to limit RAM usage on Render
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "120", "app:app"]
