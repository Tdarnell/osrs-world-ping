from contextlib import contextmanager
from typing import Any, Generator, List, Type
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import scoped_session, sessionmaker, Session, relationship, Mapped

Base: DeclarativeMeta = declarative_base()


class OSRSWorlds(Base):
    __tablename__ = "osrs_worlds"

    pkey = sa.Column(sa.Integer, primary_key=True)
    world = sa.Column(sa.String)
    world_id = sa.Column(sa.Integer, unique=True, index=True)
    world_url = sa.Column(sa.String, unique=True)
    location = sa.Column(sa.String)
    members = sa.Column(sa.Boolean)
    activity = sa.Column(sa.String)

    def __repr__(self):
        return f"<{self.__tablename__}({','.join([f'{k}={v}' for k, v in self.__dict__.items()])})>"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

    def get_ping_data(
        self, session: scoped_session[Session]
    ) -> List[Mapped[Type["PingData"]]]:
        return session.query(PingData).filter_by(world_id=self.world_id).all()


class PingData(Base):
    __tablename__ = "ping_data"
    id = sa.Column(sa.Integer, primary_key=True)
    world_id = sa.Column(sa.Integer, sa.ForeignKey("osrs_worlds.world_id"), index=True)
    timestamp = sa.Column(sa.DateTime)
    ping = sa.Column(sa.Float)
    players = sa.Column(sa.Integer)
    # add a relationship to the OSRSWorlds table
    world = relationship("OSRSWorlds")

    def __repr__(self):
        return f"<{self.__tablename__}({','.join([f'{k}={v}' for k, v in self.__dict__.items()])})>"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


@contextmanager
def get_session(
    do_not_commit: bool = False, engine=None
) -> Generator[scoped_session[Session], Any, None]:
    if not engine:
        raise ValueError("No engine provided")
    session = scoped_session(sessionmaker(bind=engine))
    try:
        yield session
    except:
        session.rollback()
        raise
    else:
        if not do_not_commit:
            session.commit()
        else:
            session.rollback()
