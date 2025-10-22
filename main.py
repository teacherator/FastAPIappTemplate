import os
from typing import Union, Annotated
from fastapi import FastAPI, Form, Depends
import pymongo
from pymongo.server_api import ServerApi
from pymongo.mongo_client import MongoClient
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel


import os

app = FastAPI()

from dotenv import load_dotenv

load_dotenv()  # take environment variables





uri = os.environ["MONGODB_URL"]
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e)

class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

db = client.FastAPI
col = db.get_collection("User_Info")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def fake_hash_password(password: str):
    return "fakehashed" + password



@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/login")
def read_root():
    return {"Hello": "World"}


@app.post("/login")
def login(username: Annotated[str, Form()], password: Annotated[str, Form()]):
    

    return  {"username": username, "password": password}
    

@app.get("/items/")
async def read_items(token: Annotated[str, Depends(oauth2_scheme)]):
    return {"token": token}


def fake_decode_token(token):
    return User(
        username=token + "fakedecoded", email="john@example.com", full_name="John Doe"
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    user = fake_decode_token(token)
    return user


@app.get("/users/me")
async def read_users_me(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user




    user = mycol.find_one({"username": username, "password": password})
    if user:
        return {"message": "Login successful"}
    else:
        return {"message": "Invalid credentials"}