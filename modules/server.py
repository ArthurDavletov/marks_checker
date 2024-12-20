import os
import re

import flask
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from flask import Flask, request, redirect, url_for, render_template

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.models import Base
from modules.parser import MarksParser


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(bind = engine)
db_session = sessionmaker(bind = engine)
db = db_session()


def is_registered():
    cookies = request.cookies
    return all(key in cookies for key in ("isu_person", "token", "PHPSESSID"))


def load_table():
    with open("temp.txt", encoding = "utf-8") as file:
        html = re.sub(r'>\s+<', '><', file.read().replace('\n', ''))
        soup = BeautifulSoup(html, "html.parser")


load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("token")
parser = MarksParser(db)


@app.route("/", methods=["GET"])
def index_get():
    if not is_registered():
        return redirect(url_for("login_get"))
    load_table()
    return render_template("index.html")


@app.route("/", methods=["POST"])
def index_post():
    if "logout" in request.form:
        parser.exit()
        resp = flask.make_response(redirect(url_for("login_get")))
        for key in ("isu_person", "token", "PHPSESSID"):
            resp.delete_cookie(key)
        return resp

@app.route("/login", methods=["GET"])
def login_get():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    if not parser.auth(login = request.form["login"], password = request.form["password"]):
        return render_template("login.html")
    resp = flask.make_response(redirect(url_for("index_get")))
    for cookie in parser.cookies:
        resp.set_cookie(key = cookie.name, value = cookie.value, expires = cookie.expires,
                        path = cookie.path, secure = cookie.secure)
    return resp

def main():
    app.run("0.0.0.0", debug = True)


if __name__ == '__main__':
    main()
