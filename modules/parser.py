import datetime
import re

import bs4.element
from bs4 import BeautifulSoup
import requests
from requests.cookies import RequestsCookieJar
from fake_useragent import UserAgent
from sqlalchemy.orm.session import Session
from werkzeug.datastructures import ImmutableMultiDict

from modules.models import Gradebook, Semester, Exam, Credit, User


class AuthMaster:
    """Класс отвечает за авторизацию пользователя."""

    __slots__ = ("__is_authed", "__cookies", "__headers", "__user_id")
    __main_url = "https://isu.uust.ru/"
    __login_url = f"{__main_url}login/"

    def __init__(self, cookies: RequestsCookieJar | ImmutableMultiDict[str, str] = None):
        self.__is_authed: bool = False
        self.__user_id: int | None = None
        self.__cookies: RequestsCookieJar = RequestsCookieJar()
        self.__headers: dict = {"User-Agent": UserAgent().random}
        if cookies is None:
            cookies = self.__generate_first_cookie()
        self.update_cookies(cookies)

    def update_cookies(self, cookies: RequestsCookieJar | ImmutableMultiDict[str, str]) -> None:
        """Обновляет куки при их наличии"""
        for cookie in cookies:
            if isinstance(cookies, RequestsCookieJar):
                if self.user_id is None and cookie.name == "isu_person":
                    self.__user_id = int(cookie.value)
                if cookie.name in self.__cookies:
                    continue
                self.__cookies.set(name = cookie.name, value = cookie.value, expires = cookie.expires,
                                   path = cookie.path, secure = cookie.secure)
            elif isinstance(cookie, str):  # передали словарь
                if self.user_id is None and cookie == "isu_person":
                    self.__user_id = int(cookies[cookie])
                if cookie in self.__cookies:
                    continue
                self.__cookies.set(name = cookie, value = cookies[cookie])

    @classmethod
    def __generate_first_cookie(cls) -> RequestsCookieJar:
        """Генерирует первые куки"""
        with requests.session() as session:
            return session.get(cls.__main_url).cookies

    def __get_form_num(self) -> int:
        """Получает специальное число с формы регистрации на сайте"""
        with requests.session() as session:
            form_num_get = session.get(self.__login_url, headers = self.__headers, cookies = self.cookies).text
            soup = BeautifulSoup(form_num_get, "html.parser")
            return int(soup.find("input", {"name": "form_num"}).get("value"))

    def auth(self, login: str, password: str) -> bool:
        """Попытка авторизации через логин и пароль.
        :param login: Логин от ЛК ИСУ УУНиТ.
        :param password: Пароль от ЛК ИСУ УУНиТ.
        :returns: ``True`` при успешной авторизации. ``False`` - при неудачной"""
        with requests.session() as session:
            data = {"form_num": self.__get_form_num(), "login": login, "password": password}
            page = session.post(self.__login_url, data = data, cookies = self.__cookies,
                                headers = self.__headers, allow_redirects = False)
            if page.status_code == 200:
                return False
            self.__is_authed = True
            page = session.post(self.__login_url, data = data, cookies = self.cookies,
                                headers = self.__headers)
            self.update_cookies(page.cookies)
            return True

    @property
    def cookies(self) -> RequestsCookieJar:
        return self.__cookies

    @property
    def user_id(self):
        return self.__user_id

    @property
    def headers(self):
        return self.__headers

    def exit(self):
        """Выход из аккаунта"""
        with requests.session() as session:
            self.__is_authed = False
            session.get(self.__main_url, params = {"exit": "exit"}, headers = self.__headers, cookies = self.__cookies)


class PageParser:
    """Класс отвечает за парсинг и актуальность страницы оценок"""

    __slots__ = ("auth_master", "db", "__marks_soup")

    __main_url = "https://isu.uust.ru/"
    __card_url = f"{__main_url}isu_person_card/"

    def __init__(self, auth_master: AuthMaster, db: Session):
        self.auth_master = auth_master
        self.db = db
        self.__marks_soup: BeautifulSoup | None = None

    def update_soup(self):
        """Обновляет soup, если сайт актуален."""
        self.__check_and_update_site(self.__get_site())

    def __check_and_update_site(self, site: str) -> None:
        """Проверяет доступность сайта и обновляет soup, если он актуален."""
        with requests.session() as session:
            session.cookies = self.auth_master.cookies
            session.headers = self.auth_master.headers
            r = session.get(site)
            if r.text == "STANDBY BAD SIGNAL":
                site = self.__find_site()
                self.__update_user_site(site)
                r = session.get(site)
            text = re.sub(r'>\s+<', '><', r.text.replace('\n', ''))
            self.__marks_soup = BeautifulSoup(text, "html.parser")

    def __get_site(self) -> str:
        """Получает сайт с оценками, добавляет его при необходимости."""
        user = self.db.query(User).filter_by(id = self.user_id).first()
        if not user:
            self.__create_user(self.user_id)
            user = self.db.query(User).filter_by(id = self.user_id).first()
        if user.site is None:  # всякое бывает, вдруг в БД не будет сайта
            user.site = self.__find_site()
            self.__update_user_site(user.site)
        return user.site

    def __create_user(self, user_id: int) -> None:
        """Создаёт нового пользователя с актуальным сайтом оценок."""
        self.db.add(User(id = user_id, site = self.__find_site()))
        self.db.commit()

    def __update_user_site(self, new_site: str) -> None:
        """Обновляет сайт для пользователя в базе данных."""
        self.db.query(User).filter_by(id = self.user_id).update({"site": new_site})
        self.db.commit()

    def __find_site(self) -> str:
        """Находит актуальный сайт и возвращает его."""
        with requests.session() as session:
            session.cookies = self.auth_master.cookies
            session.headers = self.auth_master.headers
            print(session.cookies)
            response = session.get(self.__card_url)
            soup = BeautifulSoup(response.text, "html.parser")
            button = soup.find("a", class_ = "btn-warning")
            if button and button.get("href"):
                return f"{self.__main_url}{button.get('href')}"
            raise ValueError("Не удалось найти актуальный сайт.")

    @property
    def marks_soup(self):
        return self.__marks_soup

    @property
    def user_id(self):
        return self.auth_master.user_id


class GradebookParser:
    """Класс отвечает за парсинг информации о зачётке"""

    __slots__ = ("__page_parser", "db", "__gradebook_id")

    def __init__(self, page_parser: PageParser, db: Session):
        self.__page_parser = page_parser
        self.db = db
        self.__gradebook_id: int | None = None

    def __get_from_page(self) -> dict:
        """Получает информацию из страницы на сайте."""
        self.__page_parser.update_soup()
        info = {}
        for elem in self.__page_parser.marks_soup.findAll("th", class_ = "th-student"):
            value = elem.next_sibling.string
            match elem.string:
                case "Зачетная книжка": info["gradebook_id"] = self.__gradebook_id = int(value)
                case "ФИО": info["name"] = value
                case "Код специальности": info["study_code"] = value
                case "Название специальности": info["study_name"] = value
                case "Факультет": info["faculty"] = value
                case "Дата зачисления": info["order"] = value
        self.__save_gradebook(info)
        return info

    def get_gradebook_info(self) -> dict:
        query = self.db.query(Gradebook).filter_by(user_id = self.user_id).first()
        if not query:
            info = self.__get_from_page()
            self.__save_gradebook(info)
            self.__gradebook_id = info["gradebook_id"]
            return info
        self.__gradebook_id = query.id
        return {"gradebook_id": query.id, "name": query.name, "study_code": query.study_code,
                "study_name": query.study_name, "faculty": query.faculty, "order": query.order}

    def __save_gradebook(self, info: dict):
        """Сохранение краткой информации о зачётной книжке в БД.
        Запускается лишь тогда, когда нет информации в БД"""
        self.db.add(Gradebook(id = self.gradebook_id,
                               user_id = self.user_id,
                               name = info["name"],
                               study_code = info["study_code"],
                               study_name = info["study_name"],
                               faculty = info["faculty"],
                               order = info["order"]))
        self.db.commit()

    @property
    def user_id(self):
        return self.__page_parser.user_id

    @property
    def gradebook_id(self):
        if self.__gradebook_id is None:
            self.__gradebook_id = self.get_gradebook_info()["gradebook_id"]
        return self.__gradebook_id


class MarksParser:
    """Класс отвечает за парсинг оценок на сайте"""
    __slots__ = ("db", "__gradebook_parser", "__page_parser")

    __mark_table = {"Отлично": 5, "Хорошо": 4, "Удовлетворительно": 3, "Неудовлетворительно": 2}

    def __init__(self, page_parser: PageParser, gradebook_parser: GradebookParser, db: Session):
        """Инициализирует объект парсера оценок.
        :param db: База данных SQLAlchemy
        :param page_parser: Парсер страницы с оценками"""
        self.__page_parser = page_parser
        self.__gradebook_parser = gradebook_parser
        self.db = db

    def __parse_exam(self, td: list[bs4.element.Tag]) -> Exam:
        exam = Exam()
        exam.name, exam.hours = td[1].string.strip(), td[2].string.strip()
        mark, date, signature, teacher = td[3].string, td[4].string, td[5].string, td[6].string
        if mark:
            if mark == "Зачтено":
                exam.status = True
            else:
                exam.mark = self.__mark_table.get(mark.strip())
        if date: exam.date = datetime.date.fromisoformat(date.strip())
        if signature: exam.signature = int(signature)
        if teacher: exam.teacher_name = teacher.strip()
        return exam

    def __parse_credit(self, td: list[bs4.element.Tag]) -> Credit:
        cred = Credit()
        cred.name, cred.hours = td[8].string.strip(), td[9].string.strip()
        mark, date, signature, teacher = td[10].string, td[11].string, td[12].string, td[13].string
        if mark:
            if mark == "Зачтено":
                cred.status = True
            else:
                cred.mark = self.__mark_table[mark.strip()]
        if date: cred.date = datetime.date.fromisoformat(date.strip())
        if signature: cred.signature = int(signature)
        if teacher: cred.teacher_name = teacher.strip()
        return cred

    def __fix_exams(self, exams: list[Exam], semester_id) -> list[Exam]:
        new_exams = []
        for exam in exams:
            if exam.name and self.db.query(Exam).filter((Exam.semester_id == semester_id) &
                                                        (Exam.name == exam.name)).first() is None:
                exam.semester_id = semester_id
                new_exams.append(exam)
        return new_exams

    def __fix_credits(self, credits_: list[Credit], semester_id) -> list[Credit]:
        new_credits = []
        for credit in credits_:
            if credit.name and self.db.query(Credit).filter((Credit.semester_id == semester_id) &
                                                            (Credit.name == credit.name)).first() is None:
                credit.semester_id = semester_id
                new_credits.append(credit)
        return new_credits

    def __add_semester(self, table: bs4.element.Tag):
        exams, credits_ = [], []
        for row in table.findAll("tr"):
            td = row.findAll("td")
            if not td:
                continue
            if td[1].string:
                exams.append(self.__parse_exam(td))
            if td[9].string:
                credits_.append(self.__parse_credit(td))
        if not (exams or credits_):
            return
        name = table.find("tr").string.strip()
        semester = self.db.query(Semester).filter((Semester.gradebook_id == self.gradebook_id) &
                                                  (Semester.name == name)).first()
        if semester is None:
            semester = Semester(name = name, gradebook_id = self.gradebook_id)
            self.db.add(semester)
            self.db.commit()
        exams = self.__fix_exams(exams, semester.id)
        credits_ = self.__fix_credits(credits_, semester.id)
        if exams:
            self.db.add_all(exams)
        if credits_:
            self.db.add_all(credits_)
        self.db.commit()

    def save_semesters(self):
        """Сохраняем информацию о предметах"""
        for detail in self.__page_parser.marks_soup.findAll("details"):
            t = detail.table.find("tr")
            name = t.string.strip()
            if name.startswith("Семестр"):
                self.__add_semester(detail.table)

    def get_marks(self) -> dict:
        self.__page_parser.update_soup()
        self.save_semesters()
        context = {"semesters": {}, "mean": 0}
        n = 0
        semesters = self.db.query(Semester).filter_by(gradebook_id = self.gradebook_id)
        for semester in semesters:
            context["semesters"][semester.name] = {"exams": [], "credits": []}
            exams = self.db.query(Exam).filter_by(semester_id = semester.id)
            for exam in exams:
                if exam.mark:
                    context["mean"] = (context["mean"] * n + exam.mark) / (n + 1)
                    n += 1
                context["semesters"][semester.name]["exams"].append({
                    "name": exam.name,
                    "hours": exam.hours,
                    "date": datetime.date.strftime(exam.date, "%d.%m.%Y") if exam.date else "",
                    "mark": exam.mark if exam.mark else "Зачтено" if exam.status else "",
                    "signature": exam.signature if exam.signature else "",
                    "teacher": exam.teacher_name if exam.teacher_name else ""
                })
            credits_ = self.db.query(Credit).filter_by(semester_id = semester.id)
            for credit in credits_:
                if credit.mark:
                    context["mean"] = (context["mean"] * n + credit.mark) / (n + 1)
                    n += 1
                context["semesters"][semester.name]["credits"].append({
                    "name": credit.name,
                    "hours": credit.hours,
                    "date": datetime.date.strftime(credit.date, "%d.%m.%Y") if credit.date else "",
                    "mark": credit.mark if credit.mark else "Зачтено" if credit.status else "",
                    "signature": credit.signature if credit.signature else "",
                    "teacher": credit.teacher_name if credit.teacher_name else ""
                })
        context["mean"] = round(context["mean"], 2)
        return context

    @property
    def user_id(self):
        return self.__page_parser.user_id

    @property
    def gradebook_id(self):
        return self.__gradebook_parser.gradebook_id


class ISUParser:
    """Отвечает за взаимодействие с сайтом"""

    __slots__ = ("db", "auth_master", "__page_parser", "gradebook_parser", "marks_parser")

    def __init__(self, db: Session, cookies: RequestsCookieJar | ImmutableMultiDict[str, str] | None = None):
        self.db = db
        self.auth_master = AuthMaster(cookies)
        self.__page_parser = PageParser(self.auth_master, db)
        self.gradebook_parser = GradebookParser(self.__page_parser, db)
        self.marks_parser = MarksParser(self.__page_parser, self.gradebook_parser, db)
        self.__page_parser.update_soup()
