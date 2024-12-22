FROM python:alpine

RUN apk add py3-flask

COPY . .

RUN sh build.sh

CMD ["python3", "main.py"]