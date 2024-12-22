import datetime
import re

import bs4.element
import requests
from fake_useragent import UserAgent
from bs4 import BeautifulSoup
from requests.cookies import RequestsCookieJar
from sqlalchemy.orm.session import Session
from werkzeug.datastructures import ImmutableMultiDict

from modules.models import Gradebook, Semester, Exam, Credit, User


class MarksParser:
    __slots__ = ("headers", "cookies", "form_num", "db", "gradebook_soup", "__in_account", "gradebook_id", "user_id")

    __main_url = "https://isu.uust.ru/"
    __login_url = f"{__main_url}login/"
    __card_url = f"{__main_url}isu_person_card/"
    __mark_table = {"Отлично": 5, "Хорошо": 4, "Удовлетворительно": 3, "Неудовлетворительно": 2}

    def __init__(self, db: Session, user_id: int = None, gradebook_id: int = None):
        """Инициализирует объект парсера.
        :param db: База данных SQLAlchemy
        :param user_id: Идентификатор пользователя. Или же isu_person
        :param gradebook_id: Номер зачётной книжки. Он находится в таблице с краткой информацией"""
        self.user_id = user_id
        self.gradebook_id = gradebook_id
        self.__in_account = False
        self.db = db
        self.gradebook_soup = None
        self.form_num = None
        self.headers = {"User-Agent": UserAgent().random}
        self.cookies = RequestsCookieJar()

    def update_gradebook_id(self):
        for elem in self.gradebook_soup.findAll("th", class_ = "th-student"):
            value = elem.next_sibling.string
            if elem.string == "Зачетная книжка":
                self.gradebook_id = int(value)
                break

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
        if signature: exam.signature = signature.strip()
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
        if signature: cred.signature = signature.strip()
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

    def save_gradebook(self):
        """Сохраняем информацию о зачётной книжке и предметов"""
        with requests.session() as session:
            session.cookies = self.cookies
            if self.user_id is None:
                for c, value in self.cookies.items():
                    if c == "isu_person":
                        self.user_id = int(value)
                        break
            session.headers = self.headers
            card_text = session.get(self.__card_url).text
            button = BeautifulSoup(card_text, "html.parser").find("a", class_ = "btn-warning")
            site = f"{self.__main_url}{button.get("href")}"
            html_text = re.sub(r'>\s+<', '><', session.get(site).text.replace('\n', ''))
            self.gradebook_soup = BeautifulSoup(html_text, "html.parser")
            self.update_gradebook_id()
            if not self.db.query(User).filter(User.id == self.user_id).first():
                self.db.add(User(id=self.user_id))
                self.db.commit()
            if not self.db.query(Gradebook).filter(Gradebook.user_id == self.user_id).first():
                self.__save_gradebook_info()
            for detail in self.gradebook_soup.findAll("details"):
                t = detail.table.find("tr")
                name = t.string.strip()
                if name.startswith("Семестр"):
                    self.__add_semester(detail.table)

    def __save_gradebook_info(self):
        """Сохранение краткой информации о зачётной книжке в БД.
        Запускается лишь тогда, когда нет информации в БД"""
        s = self.__get_gradebook_info()
        self.db.add(Gradebook(id = self.gradebook_id,
                              user_id = self.user_id,
                              name = s["name"],
                              study_code = s["study_code"],
                              study_name = s["study_name"],
                              faculty = s["faculty"],
                              order = s["order"]))
        self.db.commit()

    def __get_gradebook_info(self) -> dict:
        info = dict.fromkeys(("name", "study_code", "study_name", "faculty", "order"))
        for elem in self.gradebook_soup.findAll("th", class_ = "th-student"):
            value = elem.next_sibling.string
            match elem.string:
                case "Зачетная книжка": self.gradebook_id = int(value)
                case "ФИО": info["name"] = value
                case "Код специальности": info["study_code"] = value
                case "Название специальности": info["study_name"] = value
                case "Факультет": info["faculty"] = value
                case "Дата зачисления": info["order"] = value
        return info

    def get_marks(self) -> dict:
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
