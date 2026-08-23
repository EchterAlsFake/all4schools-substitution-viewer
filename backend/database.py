from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine, delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class LearnedCourse(Base):
    __tablename__ = "learned_courses"
    __table_args__ = (UniqueConstraint("school_year", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_year: Mapped[str] = mapped_column(String(9), index=True)
    code: Mapped[str] = mapped_column(String(64))


class LearnedTeacherName(Base):
    __tablename__ = "learned_teacher_names"
    __table_args__ = (UniqueConstraint("school_year", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    school_year: Mapped[str] = mapped_column(String(9), index=True)
    name: Mapped[str] = mapped_column(String(200))


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    message: Mapped[str] = mapped_column(String(1_500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FeedbackRateWindow(Base):
    __tablename__ = "feedback_rate_windows"

    window_start: Mapped[str] = mapped_column(String(16), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)


class Database:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False, "timeout": 30},
        )
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def initialize(self) -> None:
        Base.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        database_session = self._sessions()
        try:
            yield database_session
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise
        finally:
            database_session.close()

    def learned_courses(self, school_year: str) -> list[str]:
        with self.session() as session:
            return list(
                session.scalars(
                    select(LearnedCourse.code)
                    .where(LearnedCourse.school_year == school_year)
                    .order_by(LearnedCourse.code.collate("NOCASE"))
                )
            )

    def learned_teacher_names(self, school_year: str) -> list[str]:
        with self.session() as session:
            return list(
                session.scalars(
                    select(LearnedTeacherName.name).where(
                        LearnedTeacherName.school_year == school_year
                    )
                )
            )

    def import_teacher_names(self, school_year: str, teacher_names: set[str]) -> int:
        year_parts = school_year.split("-", maxsplit=1)
        if (
            len(year_parts) != 2
            or not all(part.isdigit() and len(part) == 4 for part in year_parts)
            or int(year_parts[1]) != int(year_parts[0]) + 1
        ):
            raise ValueError("invalid_school_year")
        if len(teacher_names) > 2_000:
            raise ValueError("too_many_teacher_names")
        if any(
            not isinstance(name, str)
            or not 2 <= len(name) <= 200
            or name != name.strip()
            or any(ord(character) < 32 for character in name)
            for name in teacher_names
        ):
            raise ValueError("invalid_teacher_name")

        added = 0
        with self.session() as session:
            for name in sorted(teacher_names, key=str.casefold):
                result = session.execute(
                    sqlite_insert(LearnedTeacherName)
                    .values(school_year=school_year, name=name)
                    .on_conflict_do_nothing(index_elements=["school_year", "name"])
                )
                if result.rowcount == 1:
                    added += 1
            session.execute(
                delete(LearnedCourse).where(LearnedCourse.school_year != school_year)
            )
            session.execute(
                delete(LearnedTeacherName).where(
                    LearnedTeacherName.school_year != school_year
                )
            )
        return added

    def learn(self, school_year: str, courses: set[str], teacher_names: set[str]) -> None:
        with self.session() as session:
            for code in courses:
                session.execute(
                    sqlite_insert(LearnedCourse)
                    .values(school_year=school_year, code=code)
                    .on_conflict_do_nothing(index_elements=["school_year", "code"])
                )
            for name in teacher_names:
                session.execute(
                    sqlite_insert(LearnedTeacherName)
                    .values(school_year=school_year, name=name)
                    .on_conflict_do_nothing(index_elements=["school_year", "name"])
                )
            session.execute(
                delete(LearnedCourse).where(LearnedCourse.school_year != school_year)
            )
            session.execute(
                delete(LearnedTeacherName).where(
                    LearnedTeacherName.school_year != school_year
                )
            )

    def consume_feedback_rate_limit(self, limit: int = 30) -> bool:
        window = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        with self.session() as session:
            session.execute(
                sqlite_insert(FeedbackRateWindow)
                .values(window_start=window, request_count=1)
                .on_conflict_do_update(
                    index_elements=["window_start"],
                    set_={"request_count": FeedbackRateWindow.request_count + 1},
                )
            )
            count = session.scalar(
                select(FeedbackRateWindow.request_count).where(
                    FeedbackRateWindow.window_start == window
                )
            )
            return bool(count and count <= limit)

    def save_feedback(self, message: str) -> None:
        now = datetime.now(timezone.utc)
        with self.session() as session:
            session.add(Feedback(message=message, created_at=now))

    def cleanup(self, school_year: str | None = None) -> None:
        feedback_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        rate_cutoff = (datetime.now(timezone.utc) - timedelta(days=1)).strftime(
            "%Y-%m-%dT%H:%M"
        )
        with self.session() as session:
            if school_year is not None:
                session.execute(
                    delete(LearnedCourse).where(
                        LearnedCourse.school_year != school_year
                    )
                )
                session.execute(
                    delete(LearnedTeacherName).where(
                        LearnedTeacherName.school_year != school_year
                    )
                )
            session.execute(delete(Feedback).where(Feedback.created_at < feedback_cutoff))
            session.execute(
                delete(FeedbackRateWindow).where(
                    FeedbackRateWindow.window_start < rate_cutoff
                )
            )
