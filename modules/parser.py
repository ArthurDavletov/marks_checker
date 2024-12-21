import re

import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from requests.cookies import RequestsCookieJar
from sqlalchemy.orm.session import Session
from sqlalchemy.orm.sync import update
from werkzeug.datastructures import ImmutableMultiDict

from modules.models import Gradebook


class MarksParser:
    __slots__ = ("headers", "cookies", "form_num", "db", "gradebook_soup", "__in_account")

    __main_url = "https://isu.uust.ru/"
    __login_url = f"{__main_url}login/"
    __card_url = f"{__main_url}isu_person_card/"

    def __init__(self, db: Session):
        """Инициализирует объект парсера.
        :param db: База данных SQLAlchemy"""
        self.__in_account = False
        self.db = db
        self.gradebook_soup = None
        self.form_num = None
        self.headers = {"User-Agent": UserAgent().random}
        self.cookies = RequestsCookieJar()

    def __update_first_cookies(self) -> None:
        """Обновляет значение PHP-сессии в куки."""
        with requests.session() as session:
            r = session.get(self.__main_url)
            self.cookies.update(r.cookies)

    def auth(self, login: str, password: str) -> bool:
        """Попытка авторизации через логин и пароль.
        :param login: Логин от ЛК ИСУ УУНиТ.
        :param password: Пароль от ЛК ИСУ УУНиТ.
        :returns: True при успешной авторизации. False - при неудачной"""
        if "PHPSESSID" not in self.cookies:
            self.__update_first_cookies()
        with requests.session() as session:
            form_num_get = session.get(self.__login_url, headers = self.headers, cookies = self.cookies).text
            soup = BeautifulSoup(form_num_get, "html.parser")
            self.form_num = int(soup.find("input", {"name": "form_num"}).get("value"))
            data = {"form_num": self.form_num, "login": login, "password": password}
            page = session.post(self.__login_url, data = data, cookies = self.cookies,
                                headers = self.headers, allow_redirects = False)
            if page.status_code == 200:
                return False
            self.__in_account = True
            page = session.post(self.__login_url, data = data, cookies = self.cookies,
                                headers = self.headers)
            self.update_cookies(page.cookies)
            self.save_gradebook()
            return True

    def exit(self):
        """Выход из аккаунта"""
        with requests.session() as session:
            self.__in_account = False
            session.get(self.__main_url, params = {"exit": "exit"}, headers = self.headers, cookies = self.cookies)

    def __del__(self):
        if self.__in_account:
            self.exit()

    def update_cookies(self, cookies: RequestsCookieJar | ImmutableMultiDict[str, str]):
        for cookie in cookies:
            if isinstance(cookies, RequestsCookieJar):
                if cookie.name not in self.cookies:
                    self.cookies.set(name = cookie.name, value = cookie.value, expires = cookie.expires,
                                     path = cookie.path, secure = cookie.secure)
            elif isinstance(cookie, str):
                if cookie not in self.cookies:
                    self.cookies.set(name=cookie, value = cookies[cookie])
        self.save_gradebook()

    def save_gradebook(self):
        """Сохраняем информацию о зачётной книжке и предметов"""
        with requests.session() as session:
            session.cookies = self.cookies
            for c, value in self.cookies.items():
                if c == "isu_person":
                    isu_person = int(value)
                    break
            session.headers = self.headers
            card_text = session.get(self.__card_url).text
            button = BeautifulSoup(card_text, "html.parser").find("a", class_ = "btn-warning")
            site = f"{self.__main_url}{button.get("href")}"
            html_text = re.sub(r'>\s+<', '><', session.get(site).text.replace('\n', ''))
            self.gradebook_soup = BeautifulSoup(html_text, "html.parser")
            if not self.db.query(Gradebook).filter(Gradebook.user_id == isu_person).first():
                self.__save_gradebook_info()

    def find_gradebook_id(self):
        for elem in self.gradebook_soup.findAll("th", class_ = "th-student"):
            value = elem.next_sibling.string
            if elem.string == "Зачетная книжка":
                return int(value)

    def __save_gradebook_info(self):
        """Сохранение краткой информации о зачётной книжке в БД.
        Запускается лишь тогда, когда нет информации в БД"""
        gradebook_id, name, study_code, study_name, faculty, order = 0, None, None, None, None, None
        isu_id = int(self.cookies.get("isu_person"))
        for elem in self.gradebook_soup.findAll("th", class_ = "th-student"):
            value = elem.next_sibling.string
            match elem.string:
                case "Зачетная книжка": gradebook_id = int(value)
                case "ФИО": name = value
                case "Код специальности": study_code = value
                case "Название специальности": study_name = value
                case "Факультет": faculty = value
                case "Дата зачисления": order = value
        self.db.add(Gradebook(id = gradebook_id,
                              user_id = isu_id,
                              name = name,
                              study_code = study_code,
                              study_name = study_name,
                              faculty = faculty,
                              order = order))
        self.db.commit()

if __name__ == '__main__':
    pass
