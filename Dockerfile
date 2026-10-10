FROM python:3.14-slim

# Set working directory inside container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure the data directory exists for SQLite storage
RUN mkdir -p /app/data

# Run the root entry point (which triggers migrations and boots ScumBot)
CMD ["python", "main.py"]