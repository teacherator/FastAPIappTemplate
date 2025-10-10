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




@app.get("/items/{item_id}")
def read_item(item_id: Union[str, None] = None):
    return {item_id}
