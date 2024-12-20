from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key = True, unique = True)
    gradebooks: Mapped[list["Gradebook"]] = relationship("Gradebook", back_populates = "user")


class Gradebook(Base):
    __tablename__ = "gradebooks"

    id: Mapped[int] = mapped_column(primary_key = True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str]
    study_code: Mapped[str]
    study_name: Mapped[str]
    faculty: Mapped[str]
    order: Mapped[str]
    user: Mapped["User"] = relationship("User", back_populates = "gradebooks")


class Semester(Base):
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key = True, autoincrement = True)
    name: Mapped[str]
    hours: Mapped[str]
    status: Mapped[bool | None]
    mark: Mapped[int | None]
    signature: Mapped[str | None]
    teacher_name: Mapped[str | None]
