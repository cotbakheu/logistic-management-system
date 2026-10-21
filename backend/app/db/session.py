from fastapi import Depends
from typing import Annotated

from sqlmodel import Session, create_engine

from core.config import settings

database_url = f"postgresql+psycopg://{settings.DATABASE_URL}"

engine = create_engine(database_url)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
