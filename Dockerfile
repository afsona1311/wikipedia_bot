FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# BOT_TOKEN is injected at runtime via Railway environment variables.
# Do not pass secrets at build time.
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
