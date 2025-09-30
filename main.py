from typing import Union, Annotated
from fastapi import FastAPI, Form
import pymongo

app = FastAPI()

myclient = pymongo.MongoClient("mongodb://localhost:27017/")
mydb = myclient["mydatabase"]
mycol = mydb["users"]

@app.get("/")
def read_root():
    mycol.insert_one({"user": "user", "password": "pass"})

    return {"Hello": "World"}


@app.get("/login")
def read_root():
    return {"Hello": "World"}


@app.post("/submit_form/")
async def submit_form(username: Annotated[str, Form()], email: Annotated[str, Form()]):
    return {"message": f"Received username: {username}, email: {email}"}



@app.get("/items/{item_id}")
def read_item(item_id: int, q: Union[str, None] = None):
    return {"item_id": item_id, "q": q}
