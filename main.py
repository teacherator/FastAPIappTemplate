import email
import os
from typing import Annotated
from uuid import UUID, uuid4
from fastapi import FastAPI, Depends, HTTPException, status, Form, Response
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
from datetime import datetime
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.session_verifier import SessionVerifier
import re
from fastapi import Form
from fastapi.templating import Jinja2Templates
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware


# Load env variables
load_dotenv()
MONGO_URI = os.environ.get("MONGODB_URL")
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY", "supersecret")


templates = Jinja2Templates(directory="templates")





# MongoDB setup
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(),server_api=ServerApi("1"))
db = client.FastAPI
user_col = db.get_collection("User_Info")

verification_col = db.get_collection("email_verification")

# Create TTL index: delete verification entries after 10 minutes
verification_col.create_index("created_at", expireAfterSeconds=600)


try:
    client.admin.command('ping')
    print("Connected to MongoDB!")
except Exception as e:
    print("MongoDB connection error:", e)

# FastAPI setup
app = FastAPI()
password_hash = PasswordHash.recommended()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sizebud.com", "https://fastapi-template-app-entxr.ondigitalocean.app"],  # replace with your frontend URL
    allow_credentials=True,  # required to send cookies
    allow_methods=["*"],
    allow_headers=["*"],
)


# User models
class User(BaseModel):
    email: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

class SessionData(BaseModel):
    email: str
    session_id: UUID | None = None

# Session backend & cookie
cookie_sizebud = SessionCookie(
    cookie_name="fastapi_session",
    identifier="basic-cookie",
    secret_key=SESSION_SECRET_KEY,
    cookie_params=CookieParameters(
        domain=".sizebud.com",
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    ),
)

cookie_do = SessionCookie(
    cookie_name="fastapi_session",
    identifier="basic-cookie",
    secret_key=SESSION_SECRET_KEY,
    cookie_params=CookieParameters(
        domain=".ondigitalocean.app",
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
    ),
)


backend = InMemoryBackend[UUID, SessionData]()  # In-memory for now


# Password helpers
def get_password_hash(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


async def get_session_id(
    sizebud: UUID | None = Depends(cookie_sizebud),
    do: UUID | None = Depends(cookie_do),
):
    if not sizebud and not do:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return sizebud or do


# Routes
@app.get("/")
async def root():
    routes = [{"path": route.path, "methods": list(route.methods)} for route in app.routes]
    return {"message": "API is running", "routes": routes}

@app.post("/login")
async def login(
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    response: Response
    ):
    user = user_col.find_one({"email": email})
    if not user or not verify_password(password, user["hashed_password"]):
        raise HTTPException( status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    session_id = uuid4()
    session_data = SessionData(email=email, session_id=session_id)
    await backend.create(session_id, session_data)
    cookie_sizebud.attach_to_response(response, session_id)
    cookie_do.attach_to_response(response, session_id)
    return JSONResponse({"message": "Login successful"})



@app.post("/register")
async def register_user(
    password: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    app_name: Annotated[str, Form()] = None,
):
    if user_col.find_one({"email": email}):
        raise HTTPException(400, "Email already exists")

    match = re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email)
    if not match:
        raise HTTPException(400, "Invalid email format")

    apps = db.get_collection("apps")
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    hashed_password = get_password_hash(password)


    # Generate 6-digit email code
    auth_code = random.randint(100000, 999999)

    # Send email (unchanged)
    sender_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = email

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
    html_content = html_content.replace("{{app_name}}", app_name)
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

    # Store the verification info securely in MongoDB
    verification_col.insert_one({
        "email": email,
        "auth_code": str(auth_code),
        "hashed_password": hashed_password,
        "app_name": app_name,
        "level": "user",
        "created_at": datetime.utcnow()        # TTL cleanup
    })

    return {"message": "Verification code sent"}


@app.post("/verify_email")
async def verify_email(
    email: Annotated[str, Form()],
    code: Annotated[str, Form()],
):
    record = verification_col.find_one({"email": email})

    if not record:
        raise HTTPException(404, "Verification code expired or not found")

    if record["auth_code"] != code:
        raise HTTPException(400, "Invalid verification code")

    # Insert into user database
    user_col.insert_one({
    "hashed_password": record["hashed_password"],
    "email": email,
    "disabled": False,
    "apps": [record["app_name"]],  # <-- list of apps
    "type": record["level"]
    })

    # Add user to app collections
    target_db = client[record["app_name"]]
    for col in target_db.list_collection_names():
        if col == "User_Info":
            continue
        target_db[col].insert_one({"userId": email})

    # Remove verification record
    verification_col.delete_one({"email": email})

    return {"message": "User registered successfully"}


    
# --- Session Verifier ---
class BasicVerifier(SessionVerifier[UUID, SessionData]):
    identifier = "basic-cookie"
    auto_error = True

    def __init__(self, backend: InMemoryBackend[UUID, SessionData]):
        self._backend = backend

    @property
    def backend(self):
        return self._backend

    @property
    def auth_http_exception(self):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    async def verify_session(self, session_id: UUID) -> SessionData:
        session = await self.backend.read(session_id)
        if not session:
            raise self.auth_http_exception
        return session



verifier = BasicVerifier(backend=backend)

# --- /me route ---
@app.get("/me")
async def me(
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier),
):
    return {"email": session_data.email}


@app.post("/logout")
async def logout(
    response: Response,
    session_id: UUID = Depends(get_session_id),
):
    await backend.delete(session_id)
    cookie_sizebud.delete_from_response(response)
    cookie_do.delete_from_response(response)
    return {"message": "Logged out"}


@app.post("/create_app")
async def create_app(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")
    
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
    
    user_col.update_one(
    {"email": session_data.email},
    {"$push": {"apps": app_name}}
    )
    
    # Create the new database
    new_db = client[app_name]
    new_db.create_collection("default_collection")  # optional default


    return {"message": "App created successfully"}



@app.post("/add_collection")
async def add_collection(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")
    
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    # Create collection
    target_db = client[app_name]
    if collection_name in target_db.list_collection_names():
        raise HTTPException(400, "Collection already exists")

    target_db.create_collection(collection_name)

    # Convert cursor → list
    app_users = list(user_col.find({"app": app_name}))

    # Default documents
    objects = [{"userId": user["email"]} for user in app_users]

    if objects:
        collection = target_db[collection_name]
        collection.insert_many(objects)

    return {
        "message": "Collection added and userId objects created successfully",
        "objects_created": len(objects)
    }



@app.post("/delete_collection")
async def delete_collection(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")

    # Only developer of that app can delete collections
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    # Verify admin password
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(401, "Incorrect admin password")

    # App must exist
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    # Target DB
    target_db = client[app_name]

    # Collection must exist
    if collection_name not in target_db.list_collection_names():
        raise HTTPException(404, "Collection does not exist")

    # Drop it
    target_db[collection_name].drop()

    return {"message": "Collection deleted successfully"}

@app.get("/list_collections")
async def list_collections(
    app_name: str,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")

    # Only developer of that app can list collections
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    # App must exist
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    # Target DB
    target_db = client[app_name]

    collections = target_db.list_collection_names()

    return {"collections": collections}


@app.get("/apps")
async def list_apps(
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")

    app_list = list(apps.find({}, {"_id": 0}))

    return {"apps": app_list}


@app.post("/update_object")
async def update_object(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    userId: Annotated[str, Form()],
    obj: Annotated[str, Form()],      # JSON as string
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier),
):
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")

    # Only developer of this app
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    # App must exist
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    # Select DB + collection
    target_db = client[app_name]
    if collection_name not in target_db.list_collection_names():
        raise HTTPException(404, "Collection does not exist")

    collection = target_db[collection_name]

    # Parse JSON string into dict
    import json
    try:
        obj_dict = json.loads(obj)
    except:
        raise HTTPException(400, "Invalid JSON in obj")

    # See if user exists
    existing = collection.find_one({"userId": userId})
    if not existing:
        raise HTTPException(404, "UserId not found in collection")

    # Update (append / merge fields)
    collection.update_one(
        {"userId": userId},
        {"$set": obj_dict}
    )

    return {"message": "Object merged into userId successfully"}

@app.post("/delete_app")
async def delete_app(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")
    
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password"
        )
    # Only developer of that app can delete it
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    apps.delete_one({"app_name": app_name})
    client.drop_database(app_name)
    user_col.delete_many({"app": app_name})
    
    return {"message": "App and associated data deleted successfully"}


@app.post("/delete_user")
async def delete_user(
    admin_password: Annotated[str, Form()],
    email: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
): 
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")
    
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password"
        )

    # Only developer of that app can delete users
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    if not re.match('^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email):
        raise HTTPException(400, "Invalid email format")
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")
    user = user_col.find_one({"email": email, "app": app_name})
    if not user:
        raise HTTPException(404, "User not found")
    user_col.delete_one({"email": email, "app": app_name})
    target_db = client[app_name]
    collections = target_db.list_collection_names()
    for col in collections:
        if col in ["User_Info"]:
            continue  # skip system collections
        collection = target_db[col]
        collection.delete_many({"userId": email})
    
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
async def reset_password(
    email: Annotated[str, Form()],
):
    user = user_col.find_one({"email": email})
    if not user:
        raise HTTPException(404, "User not found")
    
        # Generate 6-digit email code
    auth_code = random.randint(100000, 999999)

    # Send email (unchanged)
    sender_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    receiver_email = email

    app_name = user.get("apps", [None])[0]  # Get first app or None

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
    html_content = html_content.replace("{{app_name}}", app_name)
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

    # Store the verification info securely in MongoDB
    verification_col.insert_one({
        "email": email,
        "auth_code": str(auth_code),
        "created_at": datetime.utcnow()        # TTL cleanup
    })

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

    # Update password in user database
    hashed_password = get_password_hash(new_password)
    user_col.update_one(
        {"email": email},
        {"$set": {"hashed_password": hashed_password}}
    )

    # Remove verification record
    verification_col.delete_one({"email": email})

    return {"message": "Password reset successfully"}

@app.post("/transfer_app_ownership")
async def transfer_app_ownership(
    admin_password: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    new_developer_email: Annotated[str, Form()],
    response: Response,
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as developer
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "developer":
        raise HTTPException(403, "You must be logged in as an developer")
    
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password"
        )
    # Only developer of that app can transfer ownership
    if app_name not in logged_in_user.get("apps", []):
        raise HTTPException(403, "You must be a developer of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    new_developer = user_col.find_one({"email": new_developer_email, "app": app_name})
    if not new_developer:
        raise HTTPException(404, "New developer user not found in this app")

    # Update roles
    # Remove app from current developer
    user_col.update_one(
        {"email": session_data.email},
        {"$pull": {"apps": app_name}}
    )

    # Add app to new developer
    user_col.update_one(
        {"email": new_developer_email},
        {"$addToSet": {"apps": app_name}}  # prevents duplicates
    )


    return {"message": "App ownership transferred successfully"}



@app.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    # Ensure developer access
    user = user_col.find_one({"email": session_data.email})
    if not user or user.get("type") != "developer":
        raise HTTPException(403, "Developers only")

    # Fetch data
    apps = list(db.get_collection("apps").find({}, {"_id": 0}))
    
    # Example stats per app
    app_stats = []
    for app in apps:
        app_name = app["app_name"]
        users_count = user_col.count_documents({"app": app_name})
        collections_count = len(client[app_name].list_collection_names())
        app_stats.append({
            "app_name": app_name,
            "users": users_count,
            "collections": collections_count
        })

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "developer_email": session_data.email,
        "app_stats": app_stats
    })

@app.post("/change_user_type")
async def change_user_type(
    admin_password: Annotated[str, Form()],
    target_email: Annotated[str, Form()],
    new_type: Annotated[str, Form()],
    app_name: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(get_session_id),
    session_data: SessionData = Depends(verifier)
):
    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")
    
    admin_user = user_col.find_one({"email": "admin"})
    if not verify_password(admin_password, admin_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect admin password"
        )

    if new_type not in ["admin", "user", "developer"]:
        raise HTTPException(400, "Invalid user type")

    target_user = user_col.find_one({"email": target_email, "app": app_name})
    if not target_user:
        raise HTTPException(404, "Target user not found in this app")

    user_col.update_one(
        {"email": target_email, "app": app_name},
        {"$set": {"type": new_type}}
    )

    return {"message": "User type updated successfully"}

