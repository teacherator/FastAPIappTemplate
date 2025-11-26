import os
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, status, Form, Response
from pydantic import BaseModel
from pwdlib import PasswordHash
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# FastAPI sessions imports (v0.3.2)
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.session_verifier import SessionVerifier
import re


# Load env variables
load_dotenv()
MONGO_URI = os.environ.get("MONGODB_URL")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "supersecret")

# MongoDB setup
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(),server_api=ServerApi("1"))
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
    email: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

class SessionData(BaseModel):
    email: str

# Session backend & cookie
cookie_params = CookieParameters(
    cookie_path="/",
    secure=True,      # set to True if using HTTPS
    httponly=True,
    samesite="lax"
)

backend = InMemoryBackend[UUID, SessionData]()  # In-memory for now


# Password helpers
def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

# --- Session Cookie ---
cookie = SessionCookie(
    cookie_name="fastapi_session",
    identifier="basic-cookie",   # must match verifier
    auto_error=True,
    secret_key=SESSION_SECRET_KEY,
    cookie_params=cookie_params,
)


# Routes
@app.get("/")
async def root():
    routes = [{"path": route.path, "methods": list(route.methods)} for route in app.routes]
    return {"message": "API is running", "routes": routes}

@app.post("/register")
async def register_user(
    password: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    app_name: Annotated[str, Form()] = None,
    account_type: Annotated[str, Form()] = None,
    admin_password: Annotated[str, Form()] = None,
):

    if user_col.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists"
        )
    match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
   
    if match == None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email format"
        )

    hashed_password = get_password_hash(password)
    
    if account_type == "admin":
        # Must verify against the ONE account named "admin"
        root_admin = user_col.find_one({"email": "admin"})
        if not root_admin:
            raise HTTPException(500, "Root admin account not found")

        if not admin_password:
            raise HTTPException(401, "Admin password required")

        if not verify_password(admin_password, root_admin["hashed_password"]):
            raise HTTPException(401, "Incorrect admin password")

        level = "admin"

    else:
        level = "user"


    user_col.insert_one({
        "hashed_password": hashed_password,
        "email": email,
        "disabled": False,
        "app": app_name,
        "type": level
    })

    return {"message": "User registered successfully"}

@app.post("/login")
async def login(
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    response: Response
):
    user = user_col.find_one({"email": email})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    session_id = uuid4()
    session_data = SessionData(email=email)
    await backend.create(session_id, session_data)
    cookie.attach_to_response(response, session_id)

    response.body = b'{"message": "Login successful"}'
    response.media_type = "application/json"
    return {"message": "Login successful"}


# --- Session Verifier ---
class BasicVerifier(SessionVerifier[UUID, SessionData]):
    identifier = "basic-cookie"
    auto_error = True

    def __init__(self, backend: InMemoryBackend[UUID, SessionData]):
        self._backend = backend

    @property
    def backend(self):
        return self._backend

    async def verify_session(self, session_id: UUID, model: SessionData) -> bool:
        stored_session = await self.backend.read(session_id)
        if not stored_session:
            return False
        return stored_session.email == model.email


verifier = BasicVerifier(backend=backend)

# --- /me route ---
@app.get("/me")
async def read_current_user(
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier),
):
    user = user_col.find_one({"email": session_data.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return {
        "email": session_data.email,
        "type": user.get("type", "user")
    }


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


@app.post("/create_app")
async def create_app(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")
    
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password"
        )


    if apps.find_one({"app_name": app_name}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App name already exists"
        )
    
    apps.insert_one({
        "app_name": app_name,
        "created_by": session_data.email
    })
    
    # Create the new database
    new_db = client[app_name]
    info_collection = new_db["User_Info"]

    # Inserting a document actually creates the DB
    info_collection.insert_one({"app_name": app_name})

    return {"message": "App created successfully"}



@app.post("/add_collection")
async def add_collection(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")
    
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be logged in to an admin account of this app")


    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    target_db = client[app_name]
    if collection_name in target_db.list_collection_names():
        raise HTTPException(400, "Collection already exists")

    target_db.create_collection(collection_name)

    return {"message": "Collection added successfully"}

