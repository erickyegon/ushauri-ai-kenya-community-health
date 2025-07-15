FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements_hf.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_hf.txt

# Copy the application
COPY . .

# Create necessary directories
RUN mkdir -p memory embeddings reports logs

# Set environment variables
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Expose port
EXPOSE 7860

# Run the application
CMD ["python", "app.py"]
