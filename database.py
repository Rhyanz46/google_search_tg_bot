from typing import List, Type

import settings
import errors

from sqlalchemy import create_engine, Column, Integer, String, Sequence, Boolean, ForeignKey, TEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column

DATABASE_URL = f'mysql+mysqlconnector://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}'
Base = declarative_base()


class User(Base):
    __tablename__ = 'user'
    id = mapped_column(Integer, Sequence('user_id_seq'), primary_key=True)
    telegram_id = Column(Integer, unique=True)
    fullname = Column(String(255))
    verify_code = Column(String(50))
    verified = Column(Boolean())
    command_search: Mapped[List["CommandSearch"]] = relationship(back_populates="user")

    def get_as_dict(self) -> dict:
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "fullname": self.fullname,
        }

    def get_as_string(self) -> str:
        return f"telegram_id:{self.telegram_id}, name:{self.fullname}"


class CommandSearch(Base):
    __tablename__ = 'command_search'
    id = mapped_column(Integer, Sequence('cmd_search_id_seq'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="command_search")
    command = Column(String(300))
    keyword = Column(TEXT)
    desc = Column(TEXT)

    def get_as_string(self) -> str:
        result = f"{self.command}"
        if self.desc:
            result += f" = {self.desc}"
        return result


engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
print("connected : ", DATABASE_URL)


def save_user(telegram_id, fullname, verify_code):
    session = Session()
    user = User(telegram_id=telegram_id, fullname=fullname, verify_code=verify_code)
    session.add(user)
    session.commit()
    session.close()


def is_user_command_exist(telegram_id: int, cmd_str: str) -> bool:
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    if session.query(CommandSearch).filter_by(user_id=user.id, command=cmd_str).count():
        return True
    return False


def get_user_command(telegram_id: int, cmd_str: str) -> Type[CommandSearch] | None:
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    cmd = session.query(CommandSearch).filter_by(user_id=user.id, command=cmd_str).first()
    if cmd is None:
        return None
    return cmd


def add_user_command(telegram_id: int, cmd: CommandSearch):
    cmd.command = cmd.command.lower()
    if len(cmd.command) == 0:
        raise errors.WrongCommandFormat()
    elif cmd.command[0] != "/":
        raise errors.WrongCommandFormat()
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    if session.query(CommandSearch).filter_by(user_id=user.id, command=cmd.command).count():
        raise errors.CommandIsAlreadyExist()
    cmd.user_id = user.id
    session.add(cmd)
    session.commit()
    session.close()


def remove_user_command(telegram_id: int, cmd_str: str):
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    cmd = session.query(CommandSearch).filter_by(user_id=user.id, command=cmd_str).first()
    if cmd is None:
        raise errors.CmdNotFound()
    session.delete(cmd)
    session.commit()
    session.close()


def my_search_commands(telegram_id: int) -> list:
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    cmd = session.query(CommandSearch).filter_by(user_id=user.id).all()
    if cmd is None:
        raise errors.CmdNotFound()
    return cmd


def active_user(telegram_id, verify_code):
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    if user.verify_code != verify_code:
        raise errors.VerifyCodeWrong()
    user.verified = True
    session.flush()
    session.commit()
    session.close()


def get_active_user(telegram_id):
    session = Session()
    user = session.query(User).filter_by(telegram_id=telegram_id).first()
    if user is None:
        raise errors.UserNotFound()
    if user.verified is not True:
        raise errors.UserNotActive()
    session.flush()
    session.commit()
    session.close()


def get_all_users():
    session = Session()
    users = session.query(User).all()
    session.close()
    users = [user.get_as_string() for user in users]
    print("users")
    print(users)
    print("users")
    return users
