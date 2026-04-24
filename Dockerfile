FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY harness/ harness/

# Workspace is persisted via a volume mount
VOLUME /app/workspace

EXPOSE 8000

CMD ["python", "-m", "harness"]
