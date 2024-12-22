FROM python

# RUN apk -U upgrade
# RUN apk add py3-flask mysql mysql-client
RUN apt update && apt upgrade -y

COPY . .

RUN pip install -r requirements.txt

CMD ["python3", "main.py"]