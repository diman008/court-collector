FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml .
COPY judicial_intelligence/ judicial_intelligence/
RUN pip install --no-cache-dir .
RUN useradd -r -m app && mkdir -p /app/data && chown app:app /app/data
USER app
EXPOSE 8000
CMD ["uvicorn","judicial_intelligence.api:app","--host","0.0.0.0","--port","8000"]
