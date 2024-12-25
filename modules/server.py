import os
from time import sleep

from flask import Flask, request, redirect, url_for, render_template, make_response, g
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from modules.models import Base
from modules.parser import ISUParser


load_dotenv()
# sleep(5)
engine = create_engine(os.getenv("DATABASE_URL"))
Base.metadata.create_all(bind = engine)
DBSession = sessionmaker(bind = engine)
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_TOKEN")


def is_registered():
    """Проверка, что все куки на месте"""
    cookies = request.cookies
    return all(key in cookies for key in ("isu_person", "token", "PHPSESSID"))


@app.before_request
def before_request():
    if "db" not in g:
        g.db = DBSession()
    g.isu_parser = ISUParser(g.db, request.cookies)

@app.teardown_request
def teardown_request(exception=None):
    db = g.pop("db", None)
    if db:
        db.close()

@app.route("/", methods=["GET"])
def index_get():
    if not is_registered():
        return redirect(url_for("login_get"))
    if "isu_person" not in g.isu_parser.auth_master.cookies:
        g.isu_parser.auth_master.update_cookies(request.cookies)
    context = g.isu_parser.gradebook_parser.get_gradebook_info()
    context |= g.isu_parser.marks_parser.get_marks()
    return render_template("index.html", context = context)

@app.route("/", methods=["POST"])
def index_post():
    if "logout" in request.form:
        g.isu_parser.auth_master.exit()
        resp = make_response(redirect(url_for("login_get")))
        for key in ("isu_person", "token", "PHPSESSID"):
            resp.delete_cookie(key)
        return resp

@app.route("/login", methods=["GET"])
def login_get():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    if not g.isu_parser.auth_master.auth(login = request.form["login"], password = request.form["password"]):
        return render_template("login.html")
    resp = make_response(redirect(url_for("index_get")))
    for cookie in g.isu_parser.auth_master.cookies:
        resp.set_cookie(key = cookie.name, value = cookie.value, expires = cookie.expires,
                        path = cookie.path, secure = cookie.secure)
    return resp


def main():
    app.run("0.0.0.0", debug = True)


if __name__ == '__main__':
    main()