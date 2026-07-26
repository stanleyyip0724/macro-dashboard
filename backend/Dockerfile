FROM python:3.11-slim

# Run unprivileged: the app only ever writes to /tmp.
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R appuser:appuser /app
USER appuser

# Cloud Run injects $PORT (8080) and ignores EXPOSE; the default is only for
# local `docker run`.
ENV PORT=8080
EXPOSE 8080

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
