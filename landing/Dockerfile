FROM python:3.12-slim
WORKDIR /site
COPY public /site/public
COPY server.py /site/server.py
ENV PYTHONUNBUFFERED=1
CMD ["python", "server.py"]
