# ── Stage 1: Build React/Vite frontend ────────────────────────────────────
FROM node:22-alpine AS frontend-builder

WORKDIR /build/frontend

# Copy lockfile first so this layer is cached unless deps change
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy remaining frontend source and build
COPY frontend/ ./
RUN npm run build
# Vite default output: /build/frontend/dist/


# ── Stage 2: Production Python server ─────────────────────────────────────
FROM python:3.12-slim AS production

WORKDIR /app

# Backend source (investigator.py, diagnostics.py, server.py)
COPY backend/ ./backend/

# Scenario and diagnostic-check data files
COPY data/ ./data/

# Built frontend assets from Stage 1
COPY --from=frontend-builder /build/frontend/dist/ ./frontend/dist/

# Render injects $PORT at runtime; fall back to 10000 if running locally
EXPOSE 10000

CMD ["sh", "-c", "python backend/server.py --host 0.0.0.0 --port ${PORT:-10000}"]
