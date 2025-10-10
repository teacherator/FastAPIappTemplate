from typing import Union, Annotated
from fastapi import FastAPI, Form
import pymongo

app = FastAPI()

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["mydatabase"]
mycol = mydb["users"]

@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/login")
def read_root():
    return {"Hello": "World"}



#example url: http://127.0.0.1:8000/items/foo-item?needy=sooooneedy&skip=0&limit=10
@app.get("/items/{item_id}")
def read_item(item_id: str, needy: str, skip: int = 0, limit: int | None = None):
    print(item_id)
    item = {"item_id": item_id, "needy": needy, "skip": skip, "limit": limit}
    return item
