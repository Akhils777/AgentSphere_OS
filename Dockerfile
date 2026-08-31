FROM node:20.12.1-slim AS frontend-build
WORKDIR /src/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/run.py ./
COPY --from=frontend-build /src/frontend/dist ./frontend_dist
ENV ENVIRONMENT=production
CMD ["python", "run.py"]

