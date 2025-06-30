FROM python:3.10-slim-buster

WORKDIR /app

RUN apt-get update && apt-get install -y git

RUN git clone https://github.com/zoreu/mp3app.git .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "4"]
