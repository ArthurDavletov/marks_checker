from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from typing import List
from datetime import date


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key = True)
    gradebook: Mapped[List["Gradebook"]] = relationship("Gradebook", back_populates = "user")


class Gradebook(Base):
    __tablename__ = "gradebooks"

    id: Mapped[int] = mapped_column(primary_key = True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(100))
    study_code: Mapped[str] = mapped_column(String(8))
    study_name: Mapped[str] = mapped_column(String(100))
    faculty: Mapped[str] = mapped_column(String(100))
    order: Mapped[str] = mapped_column(String(30))
    user: Mapped["User"] = relationship("User", back_populates = "gradebook")
    semesters: Mapped[List["Semester"]] = relationship("Semester", back_populates = "gradebook")


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key = True, autoincrement = True)
    name: Mapped[str] = mapped_column(String(10))
    gradebook_id: Mapped[int] = mapped_column(ForeignKey("gradebooks.id"))
    exams: Mapped[List["Exam"]] = relationship("Exam", back_populates = "semester")
    credits: Mapped[List["Credit"]] = relationship("Credit", back_populates = "semester")
    gradebook: Mapped["Gradebook"] = relationship("Gradebook", back_populates = "semesters")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key = True, autoincrement = True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    name: Mapped[str] = mapped_column(String(100))
    hours: Mapped[int]
    status: Mapped[bool | None]
    mark: Mapped[int | None]
    date: Mapped[date | None]
    signature: Mapped[int | None]
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    semester: Mapped["Semester"] = relationship("Semester", back_populates = "exams")


class Credit(Base):
    __tablename__ = "credits"

    id: Mapped[int] = mapped_column(primary_key = True, autoincrement = True)
    semester_id: Mapped[int] = mapped_column(ForeignKey("semesters.id"))
    name: Mapped[str] = mapped_column(String(100))
    hours: Mapped[int]
    status: Mapped[bool | None]
    mark: Mapped[int | None]
    date: Mapped[date | None]
    signature: Mapped[int | None]
    teacher_name: Mapped[str | None] = mapped_column(String(100))
    semester: Mapped["Semester"] = relationship("Semester", back_populates = "credits")

if __name__ == '__main__':
    c, d = Semester(), Semester()
    print(type(c.id), type(d.id))