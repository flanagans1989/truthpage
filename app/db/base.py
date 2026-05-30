from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    __abstract__ = True

    # Prevents async greenlet errors when accessing server-generated
    # defaults (e.g. created_at, id) after flush without explicit refresh
    __mapper_args__ = {"eager_defaults": True}
