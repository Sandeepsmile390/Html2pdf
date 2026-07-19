#!/usr/bin/env bash
# Exit immediately if a command exits with a non-zero status
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Create a folder for the browser binaries
mkdir -p bin

# Define Chrome Headless Shell version and URL
# This is the official Google Chrome for Testing headless binary (Linux x64)
CHROME_VERSION="125.0.6422.141"
URL="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64/chrome-headless-shell-linux64.zip"

echo "Downloading portable Chromium Headless Shell (Version ${CHROME_VERSION})..."
curl -sSL -o chrome.zip "$URL"

echo "Extracting Chromium binary..."
unzip -o chrome.zip -d bin/
rm chrome.zip

# Grant execution permissions to the browser binary
echo "Setting execution permissions..."
chmod +x bin/chrome-headless-shell-linux64/chrome-headless-shell

echo "Download static Tailwind CSS for high-speed offline rendering..."
mkdir -p static
curl -sSL -o static/tailwind.min.css https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css

echo "Build completed successfully!"
