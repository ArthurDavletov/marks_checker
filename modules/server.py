import os

import flask
from dotenv import load_dotenv
from flask import Flask, request, redirect, url_for, render_template

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from modules.models import Base, Gradebook
from modules.parser import MarksParser


engine = create_engine("sqlite:///database.db")
Base.metadata.create_all(bind = engine)
db_session = sessionmaker(bind = engine)
db = db_session()


def is_registered():
    cookies = request.cookies
    return all(key in cookies for key in ("isu_person", "token", "PHPSESSID"))


def load_gradebook_info() -> dict:
    context = {}
    s = db.query(Gradebook).filter(Gradebook.id == parser.find_gradebook_id()).first()
    context["gradebook_id"] = s.id
    context["name"] = s.name
    context["study_code"] = s.study_code
    context["study_name"] = s.study_name
    context["faculty"] = s.faculty
    context["order"] = s.order
    return context

# with open("temp.txt", encoding = "utf-8") as file:
#     html = re.sub(r'>\s+<', '><', file.read().replace('\n', ''))
#     soup = BeautifulSoup(html, "html.parser")


load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("token")
parser = MarksParser(db)


@app.route("/", methods=["GET"])
def index_get():
    if not is_registered():
        return redirect(url_for("login_get"))
    if "isu_person" not in parser.cookies:
        parser.update_cookies(request.cookies)
    context = load_gradebook_info()
    return render_template("index.html", context = context)


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
