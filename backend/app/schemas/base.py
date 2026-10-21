from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class BaseResponse(BaseModel, Generic[DataT]):
    status: str
    message: str
    data: DataT | None = None
