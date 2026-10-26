FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
# --preload: la espera a la BD ocurre en el proceso maestro, sin timeout de worker
CMD ["gunicorn", "--preload", "-b", "0.0.0.0:8000", "app:app"]
