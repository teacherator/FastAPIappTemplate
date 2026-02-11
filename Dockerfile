# ---- frontend build ----
FROM node:20-alpine AS frontend
WORKDIR /app/Portal
COPY Portal/package*.json ./
RUN npm ci
COPY Portal/ ./
RUN npm run build

# ---- backend build ----
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy built frontend into final image
COPY --from=frontend /app/Portal/dist /app/Portal/dist

ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT} main:app"]
