import os
from typing import Union, Annotated
from fastapi import FastAPI, Form
import pymongo
import os

app = FastAPI()

from dotenv import load_dotenv

load_dotenv()  # take environment variables

client = pymongo.MongoClient(os.environ["MONGODB_URL"])
db = client.FastAPI
col = db.get_collection("User_Info")


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/login")
def read_root():
    return {"Hello": "World"}



#example url: http://127.0.0.1:8000/items/foo-item?needy=sooooneedy&skip=0&limit=10
@app.get("/items/{item_id}")
def read_item(item_id: Union[str,None]=None, needy: Union[str,None]=None , skip: int = 0, limit: int | None = None):
    print(item_id)
    item = {"item_id": item_id, "needy": needy, "skip": skip, "limit": limit}
    return item

@app.post("/login")
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    

    return  {"username": username, "password": password}
    
    # user = mycol.find_one({"username": username, "password": password})
    # if user:
    #     return {"message": "Login successful"}
    # else:
    #     return {"message": "Invalid credentials"}
    
#HIIIII :DDDDD

