FROM python:slim

# RUN apk -U upgrade
# RUN apk add py3-flask mysql mysql-client

COPY . .

RUN apt update && apt upgrade -y && apt install default-mysql-client -y && pip install -r requirements.txt

ENTRYPOINT ./entrypoint.sh python3 main.py

CMD ["python3", "main.py"]