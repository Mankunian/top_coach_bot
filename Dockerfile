FROM python:3.12-slim
WORKDIR /app
COPY backend /app/backend
COPY dist /app/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "backend.server"]
