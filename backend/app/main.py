from fastapi import FastAPI, APIRouter

# Routers
from routers import auth

app = FastAPI()

api_v1 = APIRouter(prefix="/api/v1")

api_v1.include_router(auth.router)

app.include_router(api_v1)


@app.get("/")
async def read_root():
    return {"Hello": "World"}
