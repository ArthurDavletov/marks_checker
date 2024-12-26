FROM python

# RUN apk -U upgrade
# RUN apk add py3-flask mysql mysql-client

COPY . .

RUN apt update && apt upgrade -y && pip install -r requirements.txt

ENTRYPOINT ./modules/entrypoint.sh

CMD ["python3", "main.py"]