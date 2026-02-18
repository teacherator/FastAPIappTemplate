import email
import os
from typing import Annotated
from uuid import UUID, uuid4
import json

from fastapi import FastAPI, Depends, HTTPException, status, Form, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pwdlib import PasswordHash
from dotenv import load_dotenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
from datetime import datetime, timedelta, timezone
import re
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


PORTAL_APP = "portal"


def normalize_app_name(app_name: str | None) -> str:
    if app_name is None:
        return PORTAL_APP
    cleaned = app_name.strip()
    return cleaned if cleaned else PORTAL_APP


def user_scope_query(email: str, app_name: str | None = None) -> dict:
    query = {"email": email}
    if email != "admin":
        query["app_name"] = normalize_app_name(app_name)
    return query


def app_membership_filter(app_name: str) -> dict:
    # Keep legacy "apps" support while transitioning to app-scoped accounts.
    return {"$or": [{"app_name": app_name}, {"apps": app_name}]}


def user_has_app_access(user: dict, app_name: str) -> bool:
    if user.get("type") == "admin":
        return True
    return user.get("app_name") == app_name or app_name in user.get("apps", [])


# Load env variables
load_dotenv()
MONGO_URI = os.environ.get("MONGODB_URL")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "supersecret")

templates = Jinja2Templates(directory="templates")

# MongoDB setup
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), server_api=ServerApi("1"))
db = client.FastAPI
user_col = db.get_collection("User_Info")

session_collection = db.get_collection("sessions")

verification_col = db.get_collection("email_verification")
app_request_col = db.get_collection("app_creation_requests")

verification_col.create_index("created_at", expireAfterSeconds=600)

session_collection.create_index("expires_at", expireAfterSeconds=0)
app_request_col.create_index("created_at")

try:
    client.admin.command("ping")
    print("Connected to MongoDB!")
except Exception as e:
    print("MongoDB connection error:", e)

# FastAPI setup
app = FastAPI()
password_hash = PasswordHash.recommended()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://sizebud.com",
        "https://www.sizebud.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In Docker, WORKDIR is /app
CANDIDATES = [
    Path("/app/Portal/dist"),
    Path(__file__).parent / "Portal" / "dist",
]

PORTAL_DIST = next((p for p in CANDIDATES if p.exists()), None)

if PORTAL_DIST:
    app.mount("/portal", StaticFiles(directory=str(PORTAL_DIST), html=True), name="portal")

    @app.get("/portal")
    def portal_root():
        return FileResponse(str(PORTAL_DIST / "index.html"))
else:
    @app.get("/portal")
    def portal_missing():
        return {
            "error": "Portal not built in this deployment",
            "checked": [str(p) for p in CANDIDATES],
            "cwd": os.getcwd(),
            "files_here": os.listdir("."),
        }


class User(BaseModel):
    email: str | None = None
    disabled: bool | None = None


class UserInDB(User):
    hashed_password: str


class SessionData(BaseModel):
    email: str
    app_name: str = PORTAL_APP
    session_id: UUID
    expires_at: datetime


# Cookie frontend
cookie_do = SessionCookie(
    cookie_name="fastapi_session",
    identifier="basic-cookie",
    secret_key=SESSION_SECRET_KEY,
    cookie_params=CookieParameters(
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
        max_age=3600,
    ),
)


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_session(email: str, app_name: str) -> UUID:
    session_id = uuid4()
    expires_at = utcnow() + timedelta(hours=1)

    session_collection.insert_one(
        {
            "_id": str(session_id),   # store UUID as string for consistency
            "email": email,
            "app_name": app_name,
            "expires_at": expires_at,  # datetime (timezone-aware)
        }
    )
    return session_id

def read_session(session_id: UUID) -> SessionData | None:
    doc = session_collection.find_one({"_id": str(session_id)})
    if not doc:
        return None

    expires_at = doc.get("expires_at")
    if not expires_at:
        return None

    # If expired, clean up and treat as missing
    if expires_at < utcnow():
        session_collection.delete_one({"_id": str(session_id)})
        return None

    return SessionData(
        email=doc["email"],
        app_name=doc.get("app_name", PORTAL_APP),
        session_id=session_id,
        expires_at=expires_at,
    )

def delete_session(session_id: UUID) -> None:
    session_collection.delete_one({"_id": str(session_id)})

async def get_session_id(session_id: UUID | None = Depends(cookie_do)) -> UUID:
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

async def require_session(session_id: UUID = Depends(get_session_id)) -> SessionData:
    session = read_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    return session


def get_logged_in_user(session: SessionData):
    user = user_col.find_one(user_scope_query(session.email, session.app_name))
    if user:
        return user
    # Backward compatibility for legacy accounts without app_name.
    return user_col.find_one({"email": session.email})

@app.get("/")
async def root():
    routes = [{"path": route.path, "methods": list(route.methods)} for route in app.routes]
    return {"message": "API is running", "routes": routes}


@app.post("/login")
async def login(
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    response: Response,
    app_name: Annotated[str | None, Form()] = None,
):
    scoped_app = normalize_app_name(app_name)

    if email == "admin":
        candidates = list(user_col.find({"email": email}))
    elif app_name is not None and app_name.strip() != "":
        candidates = list(
            user_col.find(
                {
                    "email": email,
                    "$or": [
                        {"app_name": scoped_app},
                        {"apps": scoped_app},
                    ],
                }
            )
        )
    else:
        # Backward-compatible mode for clients that do not send app_name.
        candidates = list(user_col.find({"email": email}))

    user = next(
        (u for u in candidates if verify_password(password, u["hashed_password"])),
        None,
    )
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    user_app = user.get("app_name") or user.get("apps", [scoped_app])[0] or scoped_app
    session_id = create_session(email, normalize_app_name(user_app))
    cookie_do.attach_to_response(response, session_id)

    return {"message": "Login successful"}


@app.post("/register")
async def register_user(
    password: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    app_name: Annotated[str | None, Form()] = None,
):
    scoped_app = normalize_app_name(app_name)

    if user_col.find_one(user_scope_query(email, scoped_app)):
        raise HTTPException(400, "Email already exists")

    match = re.match(r"^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$", email)
    if not match:
        raise HTTPException(400, "Invalid email format")

    if scoped_app != PORTAL_APP:
        apps = db.get_collection("apps")
        if not apps.find_one({"app_name": scoped_app}):
            raise HTTPException(404, "App not found")

    hashed_password = get_password_hash(password)

    # Generate 6-digit email code
    auth_code = random.randint(100000, 999999)

    sender_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = email

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
    html_content = html_content.replace("{{app_name}}", scoped_app)
    text_content = f"Your authentication code is: {auth_code}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Authentication Code"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, smtp_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

    verification_col.insert_one(
        {
            "email": email,
            "auth_code": str(auth_code),
            "hashed_password": hashed_password,
            "app_name": scoped_app,
            "level": "user",
            "created_at": utcnow(),
        }
    )

    return {"message": "Verification code sent"}


@app.post("/verify_email")
async def verify_email(
    email: Annotated[str, Form()],
    code: Annotated[str, Form()],
    app_name: Annotated[str | None, Form()] = None,
):
    scoped_app = normalize_app_name(app_name)
    record = verification_col.find_one(
        {"email": email, "$or": [{"app_name": scoped_app}, {"app_name": {"$exists": False}}]}
    )

    if not record:
        raise HTTPException(404, "Verification code expired or not found")

    if record["auth_code"] != code:
        raise HTTPException(400, "Invalid verification code")

    scoped_app = normalize_app_name(record.get("app_name"))

    user_col.insert_one(
        {
            "hashed_password": record["hashed_password"],
            "email": email,
            "app_name": scoped_app,
            "disabled": False,
            "apps": [scoped_app] if scoped_app != PORTAL_APP else [],
            "type": record["level"],
        }
    )

    if scoped_app != PORTAL_APP:
        target_db = client[scoped_app]
        for col in target_db.list_collection_names():
            if col == "User_Info":
                continue
            target_db[col].insert_one({"userId": email})

    verification_col.delete_one({"email": email})
    return {"message": "User registered successfully"}


@app.get("/me")
async def me(session: SessionData = Depends(require_session)):
    return {"email": session.email, "app_name": session.app_name}


@app.post("/logout")
async def logout(
    response: Response,
    session_id: UUID = Depends(get_session_id),
):
    delete_session(session_id)
    cookie_do.delete_from_response(response)
    return {"message": "Logged out"}


@app.post("/create_app")
async def create_app(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password",
        )

    if apps.find_one({"app_name": app_name}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App name already exists",
        )

    if session.email != "admin":
        user_col.update_one(
            user_scope_query(session.email, session.app_name),
            {"$set": {"app_name": app_name}, "$addToSet": {"apps": app_name}},
        )

    new_db = client[app_name]
    new_db.create_collection("default_collection")

    return {"message": "App created successfully"}


@app.post("/request_app_creation")
async def request_app_creation(
    app_name: Annotated[str, Form()],
    reason: Annotated[str | None, Form()] = None,
    session: SessionData = Depends(require_session),
):
    requested_app = app_name.strip().lower()
    if not re.match(r"^[a-z0-9][a-z0-9_-]{2,49}$", requested_app):
        raise HTTPException(
            status_code=400,
            detail="App name must be 3-50 chars and contain only letters, numbers, _ or -",
        )

    apps = db.get_collection("apps")
    if apps.find_one({"app_name": requested_app}):
        raise HTTPException(status_code=400, detail="App name already exists")

    existing_pending = app_request_col.find_one(
        {
            "requested_app_name": requested_app,
            "requested_by": session.email,
            "status": "pending",
        }
    )
    if existing_pending:
        raise HTTPException(status_code=409, detail="You already have a pending request for this app")

    app_request_col.insert_one(
        {
            "requested_app_name": requested_app,
            "requested_by": session.email,
            "requested_from_app": session.app_name,
            "reason": (reason or "").strip(),
            "status": "pending",
            "created_at": utcnow(),
        }
    )

    return {"message": "App creation request submitted"}


@app.post("/add_collection")
async def add_collection(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    target_db = client[app_name]
    if collection_name in target_db.list_collection_names():
        raise HTTPException(400, "Collection already exists")

    target_db.create_collection(collection_name)

    app_users = list(user_col.find(app_membership_filter(app_name)))

    objects = [{"userId": user["email"]} for user in app_users]

    if objects:
        collection = target_db[collection_name]
        collection.insert_many(objects)

    return {
        "message": "Collection added and userId objects created successfully",
        "objects_created": len(objects),
    }


@app.post("/delete_collection")
async def delete_collection(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(401, "Incorrect admin password")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    target_db = client[app_name]
    if collection_name not in target_db.list_collection_names():
        raise HTTPException(404, "Collection does not exist")

    target_db[collection_name].drop()
    return {"message": "Collection deleted successfully"}


@app.get("/list_collections")
async def list_collections(
    app_name: str,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    target_db = client[app_name]
    collections = target_db.list_collection_names()
    return {"collections": collections}


@app.get("/apps")
async def list_apps(session: SessionData = Depends(require_session)):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    app_list = list(apps.find({}, {"_id": 0}))
    return {"apps": app_list}


@app.post("/update_object")
async def update_object(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    userId: Annotated[str, Form()],
    obj: Annotated[str, Form()],
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    target_db = client[app_name]
    if collection_name not in target_db.list_collection_names():
        raise HTTPException(404, "Collection does not exist")

    collection = target_db[collection_name]

    try:
        obj_dict = json.loads(obj)
    except Exception:
        raise HTTPException(400, "Invalid JSON in obj")

    existing = collection.find_one({"userId": userId})
    if not existing:
        raise HTTPException(404, "UserId not found in collection")

    collection.update_one({"userId": userId}, {"$set": obj_dict})
    return {"message": "Object merged into userId successfully"}


@app.post("/delete_app")
async def delete_app(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect admin password")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    apps.delete_one({"app_name": app_name})
    client.drop_database(app_name)

    user_col.delete_many(app_membership_filter(app_name))

    return {"message": "App and associated data deleted successfully"}


@app.post("/delete_user")
async def delete_user(
    admin_password: Annotated[str, Form()],
    email: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect admin password")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not re.match(r"^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$", email):
        raise HTTPException(400, "Invalid email format")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    user = user_col.find_one({"email": email, "$or": [{"app_name": app_name}, {"apps": app_name}]})
    if not user:
        raise HTTPException(404, "User not found")

    user_col.delete_one({"email": email, "$or": [{"app_name": app_name}, {"apps": app_name}]})

    target_db = client[app_name]
    for col in target_db.list_collection_names():
        if col in ["User_Info"]:
            continue
        target_db[col].delete_many({"userId": email})

    return {"message": "User and associated data deleted successfully"}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_event():
    print("FastAPI app has started.")


@app.on_event("shutdown")
async def shutdown_event():
    print("FastAPI app is shutting down.")


@app.post("/reset_password")
async def reset_password(email: Annotated[str, Form()]):
    user = user_col.find_one({"email": email})
    if not user:
        raise HTTPException(404, "User not found")

    auth_code = random.randint(100000, 999999)

    sender_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = email

    app_name = user.get("app_name") or user.get("apps", [None])[0] or PORTAL_APP

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
    html_content = html_content.replace("{{app_name}}", str(app_name))
    text_content = f"Your authentication code is: {auth_code}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Authentication Code"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg.attach(MIMEText(text_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, smtp_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())

    verification_col.insert_one(
        {"email": email, "auth_code": str(auth_code), "created_at": utcnow()}
    )

    return {"message": "Verification code sent"}


@app.post("/confirm_reset_password")
async def confirm_reset_password(
    email: Annotated[str, Form()],
    code: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
):
    record = verification_col.find_one({"email": email})
    if not record:
        raise HTTPException(404, "Verification code expired or not found")

    if record["auth_code"] != code:
        raise HTTPException(400, "Invalid verification code")

    hashed_password = get_password_hash(new_password)
    user_col.update_one({"email": email}, {"$set": {"hashed_password": hashed_password}})

    verification_col.delete_one({"email": email})
    return {"message": "Password reset successfully"}


@app.post("/transfer_app_ownership")
async def transfer_app_ownership(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    new_developer_email: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    apps = db.get_collection("apps")

    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") not in ["developer", "admin"]:
        raise HTTPException(403, "You must be logged in as an developer")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect admin password")

    if not user_has_app_access(logged_in_user, app_name):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    new_developer = user_col.find_one(
        {"email": new_developer_email, "$or": [{"app_name": app_name}, {"apps": app_name}]}
    )
    if not new_developer:
        raise HTTPException(404, "New developer user not found in this app")

    user_col.update_one(
        user_scope_query(session.email, session.app_name),
        {"$pull": {"apps": app_name}, "$set": {"app_name": PORTAL_APP}},
    )
    user_col.update_one(
        {"email": new_developer_email, "$or": [{"app_name": app_name}, {"apps": app_name}]},
        {"$addToSet": {"apps": app_name}, "$set": {"app_name": app_name}},
    )

    return {"message": "App ownership transferred successfully"}


@app.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    session: SessionData = Depends(require_session),
):
    user = user_col.find_one({"email": session.email})
    if not user or user.get("type") != "developer":
        raise HTTPException(403, "Developers only")

    apps = list(db.get_collection("apps").find({}, {"_id": 0}))

    app_stats = []
    for app_doc in apps:
        app_name = app_doc["app_name"]
        users_count = user_col.count_documents(app_membership_filter(app_name))
        collections_count = len(client[app_name].list_collection_names())
        app_stats.append(
            {"app_name": app_name, "users": users_count, "collections": collections_count}
        )

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "developer_email": session.email, "app_stats": app_stats},
    )


@app.post("/change_user_type")
async def change_user_type(
    admin_password: Annotated[str, Form()],
    target_email: Annotated[str, Form()],
    new_type: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session: SessionData = Depends(require_session),
):
    logged_in_user = get_logged_in_user(session)
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")

    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect admin password")

    if new_type not in ["admin", "user", "developer"]:
        raise HTTPException(400, "Invalid user type")

    # Original used {"email": target_email, "app": app_name}; use apps list:
    target_user = user_col.find_one(
        {"email": target_email, "$or": [{"app_name": app_name}, {"apps": app_name}]}
    )
    if not target_user:
        raise HTTPException(404, "Target user not found in this app")

    user_col.update_one(
        {"email": target_email, "$or": [{"app_name": app_name}, {"apps": app_name}]},
        {"$set": {"type": new_type}},
    )

    return {"message": "User type updated successfully"}

