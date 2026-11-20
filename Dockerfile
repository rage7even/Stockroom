FROM node:24-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/angular.json frontend/tsconfig*.json ./
COPY frontend/src/ ./src/
RUN npm run build

FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STOCKROOM_DB=/data/stockroom.db
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && useradd --system --uid 10001 stockroom \
    && install -d -o stockroom -g stockroom /data
COPY backend/manage.py ./backend/
COPY backend/config/ ./backend/config/
COPY backend/inventory/ ./backend/inventory/
COPY database/week11-catalog.csv ./database/week11-catalog.csv
COPY --from=frontend-build /build/dist/stockroom/browser/ ./frontend/dist/stockroom/browser/
USER stockroom
EXPOSE 8000
CMD ["sh", "-c", "python backend/manage.py migrate --noinput && python backend/manage.py seed && python backend/manage.py seed_week11 --catalogue --if-demo && exec python backend/manage.py run_stockroom 0.0.0.0:8000 --noreload"]
