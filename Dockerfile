FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["bash", "-lc", "python -m uvicorn server:app --host 0.0.0.0 --port 8000"]
