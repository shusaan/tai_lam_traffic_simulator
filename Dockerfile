FROM python:3.10-slim

WORKDIR /app

# Create cache directory
RUN mkdir -p /root/.cache/pip

# Copy and install requirements first for better caching
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

COPY src/ ./src/
COPY *.py ./

EXPOSE 8050

ENV PYTHONPATH=/app

CMD ["python", "src/main.py", "--mode", "dashboard"]