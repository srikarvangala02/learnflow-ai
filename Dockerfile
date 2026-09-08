FROM node:22-bookworm-slim

# Chrome Headless Shell runtime libs (per Remotion's Docker guide: remotion.dev/docs/docker)
# + ffmpeg (Remotion bundles its own; apt's is a harmless fallback) + Python for the backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libdbus-1-3 libatk1.0-0 libgbm-dev libasound2 libxrandr2 \
    libxkbcommon-dev libxfixes3 libxcomposite1 libxdamage1 \
    libatk-bridge2.0-0 libpango-1.0-0 libcairo2 libcups2 \
    ffmpeg python3 python3-venv python3-pip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- render/ (Node/Remotion) ---
COPY render/package.json render/package-lock.json render/
RUN npm --prefix render ci
COPY render/ render/
RUN npx --prefix render remotion browser ensure

# --- backend/ (Python, in a venv — Debian's system Python is externally managed) ---
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/

ENV PORT=8080
EXPOSE 8080
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
