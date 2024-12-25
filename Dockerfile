FROM python:alpine

RUN apk add py3-flask

COPY . .

RUN pip install -r requirements.txt

CMD ["python3", "main.py"]
