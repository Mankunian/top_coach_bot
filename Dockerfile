FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend /app/backend
COPY dist /app/dist
ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python", "-m", "backend.server"]
