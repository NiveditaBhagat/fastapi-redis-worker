

from fastapi import FastAPI

from database import Base,engine
import models
import orders

app = FastAPI()

Base.metadata.create_all(bind=engine)

app.include_router(orders.router)

@app.get("/")
def home():
    return {"message": "E-commerce API is running"}