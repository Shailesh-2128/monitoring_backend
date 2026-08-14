# DeployOps Monitoring Backend

Django REST Framework service powering the DeployOps Monitoring Platform.

---

## Docker Deployment Setup

### Quick Start with Docker Compose

1. **Configure Environment Variables**:
   Ensure `.env` exists in `monitoring_backend` (or copy `.env.example` to `.env`):
   ```bash
   cp .env.example .env
   ```

2. **Build and Run Containers**:
   ```bash
   docker compose up --build -d
   ```

3. **Check Container Status & Logs**:
   ```bash
   docker compose ps
   docker compose logs -f monitoring_backend
   ```

4. **Stop Containers**:
   ```bash
   docker compose down
   ```

---

## Building and Running Docker Image Manually

```bash
# Build the Docker image
docker build -t deployops-monitoring-backend .

# Run container exposing port 8000
docker run -d --name monitoring_backend \
  -p 8000:8000 \
  --env-file .env \
  deployops-monitoring-backend
```

---

## Container Architecture

- **Base Image**: Python 3.12 Slim (Multi-stage build for minimal footprint and enhanced security)
- **WSGI Application Server**: Gunicorn (3 worker threads)
- **Static File Handling**: WhiteNoise middleware with compressed static storage
- **Database**: PostgreSQL (via `DATABASE_URL` in `.env`) or fallback SQLite
- **Security**: Non-root user (`appuser` UID 8888) with minimal privileges
- **Healthcheck**: Automated health check curling `http://localhost:8000/` every 30s
