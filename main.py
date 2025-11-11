import os
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, status, Form, Response
from pydantic import BaseModel
from pwdlib import PasswordHash
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# FastAPI sessions imports (v0.3.2)
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.session_verifier import SessionVerifier

# Load env variables
load_dotenv()
MONGO_URI = os.environ.get("MONGODB_URL")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "supersecret")

# MongoDB setup
client = MongoClient(MONGO_URI, server_api=ServerApi("1"))
db = client.FastAPI
user_col = db.get_collection("User_Info")

try:
    client.admin.command('ping')
    print("Connected to MongoDB!")
except Exception as e:
    print("MongoDB connection error:", e)

# FastAPI setup
app = FastAPI()
password_hash = PasswordHash.recommended()

# User models
class User(BaseModel):
    username: str
    email: str | None = None
    full_name: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

class SessionData(BaseModel):
    username: str

# Session backend & cookie
# Session backend & cookie
cookie_params = CookieParameters(
    cookie_path="/",
    secure=False,      # set to True if using HTTPS
    httponly=True,
    samesite="lax"
)

backend = InMemoryBackend[UUID, SessionData]()  # In-memory for now


# Password helpers
def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

# Routes
@app.get("/")
def read_root():
    return {"message": "Hello World"}

@app.post("/register")
async def register_user(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    full_name: Annotated[str, Form()] = None,
    email: Annotated[str, Form()] = None,
    app_name: Annotated[str, Form()] = None,
):
    if user_col.find_one({"username": username}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    hashed_password = get_password_hash(password)
    user_col.insert_one({
        "username": username,
        "hashed_password": hashed_password,
        "full_name": full_name,
        "email": email,
        "disabled": False,
        "app": app_name
    })

    return {"message": "User registered successfully"}

@app.post("/login")
async def login(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    response: Response
):
    user = user_col.find_one({"username": username})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )

    session_id = uuid4()
    session_data = SessionData(username=username)
    await backend.create(session_id, session_data)
    cookie.attach_to_response(response, session_id)

    response.body = b'{"message": "Login successful"}'
    response.media_type = "application/json"
    return {"message": "Login successful"}


# --- Session Cookie ---
cookie = SessionCookie(
    cookie_name="fastapi_session",
    identifier="basic-cookie",   # must match verifier
    auto_error=True,
    secret_key=SESSION_SECRET_KEY,
    cookie_params=cookie_params,
)

# --- Session Verifier ---
class BasicVerifier(SessionVerifier[UUID, SessionData]):
    identifier = "basic-cookie"  # ✅ match cookie identifier
    auto_error = True

    def __init__(self, backend: InMemoryBackend[UUID, SessionData]):
        self._backend = backend

    @property
    def backend(self):
        return self._backend

    async def verify_session(self, model: SessionData) -> bool:
        try:
            # Check MongoDB if user exists
            return bool(user_col.find_one({"username": model.username}))
        except Exception as e:
            print("Error in verify_session:", e)
            return False

verifier = BasicVerifier(backend=backend)

# --- /me route ---
@app.get("/me")
async def read_current_user(
    session_id: UUID = Depends(cookie),            # read cookie
    session_data: SessionData = Depends(verifier), # verify it
):
    return {"username": session_data.username}



@app.post("/logout")
async def logout(
    response: Response,
    session_id: UUID = Depends(cookie)
):
    # Delete the session from the backend (if it exists)
    try:
        await backend.delete(session_id)
    except KeyError:
        pass  # session already deleted or invalid

    # Remove the cookie from the client
    cookie.delete_from_response(response)

    return {"message": "Logged out successfully"}



