from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Parent class of every database model.

    It collects the table definitions in `Base.metadata`, which Alembic
    reads to generate migrations.
    """
