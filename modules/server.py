import time
from dotenv import load_dotenv
import bs4
from bs4 import BeautifulSoup

import re
from flask import Flask, request, redirect, url_for, session, render_template
import sqlite3
import os
import pathlib

import requests
from requests.cookies import RequestsCookieJar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver import FirefoxOptions


class Database:
    def __init__(self, db_name: str):
        self.db_name = db_name
        self.connection = sqlite3.connect(self.db_name, check_same_thread = False)
        # self.cursor = self.connection.cursor()

    def create_table(self, table_name: str, cols: dict, refs: list[list[str]] = None):
        """Создание таблицы.
        :param table_name: Название таблицы
        :param cols: Описание столбцов в виде словаря,
        где ключ - название столбца, а значения - тип -- {"ID": "INTEGER", "NAME": "TEXT"}, ...
        :param refs: Описание вторичных ключей. -- ["foreign key", "parent_table_name", "parent_key"], ...
        """
        cols_def = ", ".join(f"{col} {dtype}" for col, dtype in cols.items())
        if refs is not None:
            refs_def = ', '.join(f"FOREIGN KEY ({ref[0]}) REFERENCES {ref[1]} ({ref[2]})" for ref in refs)
            cols_def = ", ".join((cols_def, refs_def))
        query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_def})"
        cursor = self.connection.cursor()
        cursor.execute(query)
        self.connection.commit()
        cursor.close()

    def insert_data(self, table_name: str, data: list | tuple, cols: list | tuple = None):
        """Вставка данных в таблицу"""
        placeholders = ", ".join(["?"] * len(data))
        if cols is None:
            query = f"INSERT INTO {table_name} VALUES ({placeholders})"
        else:
            query = f"INSERT INTO {table_name} ({', '.join(cols)}) VALUES ({placeholders})"
        cursor = self.connection.cursor()
        cursor.execute(query, tuple(data))
        self.connection.commit()
        cursor.close()

    def select_all(self, table_name: str):
        """Вытягивание всех данных из таблицы"""
        query = f"SELECT * FROM {table_name}"
        cursor = self.connection.cursor()
        cursor.execute(query)
        data = cursor.fetchall()
        cursor.close()
        return data

    def select_only(self, table_name: str, col_name: str, value):
        """Аналог SELECT * FROM table_name WHERE col_name = value"""
        query = f"SELECT * FROM {table_name} WHERE {col_name}=?"
        cursor = self.connection.cursor()
        cursor.execute(query, (value, ))
        data = cursor.fetchall()
        cursor.close()
        return data

    def delete_only(self, table_name: str, col_name: str, value):
        """Удаление по условию, где table[col_name] == value"""
        query = f"DELETE FROM {table_name} WHERE {col_name}=?"
        cursor = self.connection.cursor()
        cursor.execute(query, (value, ))
        self.connection.commit()
        cursor.close()

    def close_connection(self):
        self.connection.close()

    def __del__(self):
        self.close_connection()

class Users:
    def __init__(self, database: Database):
        self.table_name = "users"
        self.database = database
        cols = {
            "isu_person": "INTEGER PRIMARY KEY",
            "token": "TEXT"
        }
        self.database.create_table(self.table_name, cols)

    def add_user(self, isu_person: int, token: str):
        self.database.insert_data(self.table_name, (isu_person, token))

    def find_user(self, isu_person: int):
        return self.database.select_only(self.table_name, "isu_person", isu_person)

    def delete_user(self, isu_person: int):
        self.database.delete_only(self.table_name, "isu_person", isu_person)

class Gradebooks:
    def __init__(self, database: Database):
        self.table_name = "gradebooks"
        self.database = database
        cols = {
            "gradebook": "INTEGER PRIMARY KEY",
            "isu_person": "INTEGER NOT NULL"
        }
        refs = [["isu_person", "users", "isu_person"]]
        self.database.create_table(self.table_name, cols, refs)

    def add_gradebook(self, isu_person: int, gradebook: int):
        self.database.insert_data(self.table_name, (gradebook, isu_person))

    def find_gradebook(self, gradebook: int):
        return self.database.select_only(self.table_name, "gradebook", gradebook)


def is_registered():
    if "isu_person" in session and "token" in session:
        token_search = users_table.find_user(session["isu_person"])
        if len(token_search) != 0 and session["token"] == token_search[0][1]:
            return True
    return False


def check_auth(login: str, password: str):
    script = """
            fetch('https://isu.uust.ru/login/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: 'form_num=' + arguments[0] +
                  '&login=' + encodeURIComponent(arguments[1]) +
                  '&password=' + encodeURIComponent(arguments[2]),
            },
        )
    """
    site = "https://isu.uust.ru/login/"
    options = FirefoxOptions()
    options.add_argument("--headless")
    with webdriver.Firefox(options = options) as driver:
        driver.get(site)
        value = driver.find_element(By.NAME, "form_num").get_property("value")
        driver.execute_script(script, value, login, password)
        time.sleep(3)
        cookies = driver.get_cookies()
        if len(cookies) == 1:
            return False
        isu_person, token = None, None
        for c in cookies:
            match c["name"]:
                case "isu_person":
                    isu_person = int(c["value"])
                case "token":
                    token = c["value"]
        session.update(isu_person=isu_person, token=token)
        if not users_table.find_user(isu_person):
            users_table.add_user(isu_person, token)
        return True


def child_table():
    pass


def add_table_to_database(soup: bs4.BeautifulSoup):
    for elem in soup.findAll("th", class_ = "th-student"):
        if elem.string == "Зачетная книжка":
            print(123)
            isu_person = session["isu_person"]
            gradebook_id = int(elem.next_sibling.string)
            if not gradebooks_table.find_gradebook(gradebook_id):
                gradebooks_table.add_gradebook(isu_person, gradebook_id)

    for elem in soup.findAll("details", class_="resident-spoiler-details"):
        name = elem.find("summary").string
        if not pathlib.Path("gradebooks").exists():
            pathlib.Path("gradebooks").mkdir()
        # with open(f"gradebooks/{}")


# Загрузка работает. Я пока закомментировал часть, чтобы обращаться к локальной копии
def load_table():
    # cookies = RequestsCookieJar()
    # site = "https://isu.uust.ru/"
    # for name, value in session.items():
    #     cookies.set(name, str(value))
    # r = requests.get(site + "isu_person_card/", cookies = cookies)
    # button = BeautifulSoup(r.text, "html.parser").find("a", class_ = "btn-warning")
    # new_site = site + button.get("href")
    with open("temp.txt", encoding = "utf-8") as file:
        # soup = BeautifulSoup(requests.get(new_site).text, "html.parser")
        html = re.sub(r'>\s+<', '><', file.read().replace('\n', ''))
        soup = BeautifulSoup(html, "html.parser")
        add_table_to_database(soup)

load_dotenv()
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("token")


@app.route("/", methods=["GET"])
def index_html():
    if not is_registered():
        return redirect(url_for("login_get"))
    load_table()
    return render_template("index.html")

@app.route("/login", methods=["GET"])
def login_get():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login_post():
    if not check_auth(login = request.form["login"], password = request.form["password"]):
        return render_template("login.html")
    return redirect(url_for("index_html"))

pathlib.Path("data").mkdir(exist_ok = True)
users_db = Database("data/users.db")
users_table = Users(users_db)
gradebooks_table = Gradebooks(users_db)

def main():
    app.run("0.0.0.0", debug = True)


if __name__ == '__main__':
    main()
