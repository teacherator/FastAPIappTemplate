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
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
import glob
from datetime import datetime
from fastapi_sessions.backends.implementations import InMemoryBackend
from fastapi_sessions.frontends.implementations import SessionCookie, CookieParameters
from fastapi_sessions.session_verifier import SessionVerifier
import re
from fastapi import Form
from fastapi.templating import Jinja2Templates
from fastapi import Request



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
    cookie.attach_to_response(response, session_id)
    return {"message": "Login successful"}


@app.post("/register")
async def register_user(
    password: Annotated[str, Form()],
    email: Annotated[str, Form()] = None,
    app_name: Annotated[str, Form()] = None,
    account_type: Annotated[str, Form()] = None,
    admin_password: Annotated[str, Form()] = None,
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
    
    if account_type == "admin" and not app_name:
        raise HTTPException(400, "Admin must specify an app")

    # Admin verification
    if account_type == "admin":
        root_admin = user_col.find_one({"email": "admin"})
        if not root_admin:
            raise HTTPException(500, "Root admin account not found")
        if not admin_password or not verify_password(admin_password, root_admin["hashed_password"]):
            raise HTTPException(401, "Incorrect admin password")
        level = "admin"
    else:
        level = "user"

    # Generate 6-digit email code
    auth_code = random.randint(100000, 999999)

    # Send email (unchanged)
    sender_email = ""
    receiver_email = ""
    smtp_password = ""

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
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
        "level": level,
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
        "app": record["app_name"],
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
    def backend(self) -> InMemoryBackend[UUID, SessionData]:
        return self._backend
    
    @property
    def auth_http_exception(self) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    async def verify_session(self, model: SessionData) -> bool:
        """
        Verify that the session is valid.
        """
        stored = await self.backend.read(model.session_id)
        if not stored:
            return False
        return stored.email == model.email



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
    new_db.create_collection("default_collection")  # optional default


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

    # Must be admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")
    
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be logged in to an admin account of this app")

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
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")

    # Only admin of that app can delete collections
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be an admin of this app")

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
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")

    # Only admin of that app can list collections
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be an admin of this app")

    # App must exist
    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    # Target DB
    target_db = client[app_name]

    collections = target_db.list_collection_names()

    return {"collections": collections}


@app.get("/apps")
async def list_apps(
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")

    app_list = list(apps.find({}, {"_id": 0}))

    return {"apps": app_list}


@app.post("/update_object")
async def update_object(
    app_name: Annotated[str, Form()],
    collection_name: Annotated[str, Form()],
    userId: Annotated[str, Form()],
    obj: Annotated[str, Form()],      # JSON as string
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier),
):
    apps = db.get_collection("apps")

    # Must be logged in as admin
    logged_in_user = user_col.find_one({"email": session_data.email})
    if not logged_in_user or logged_in_user.get("type") != "admin":
        raise HTTPException(403, "You must be logged in as an admin")

    # Only admin of this app
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be an admin of this app")

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
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

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
    # Only admin of that app can delete it
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be logged in to an admin account of this app")

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
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
): 
    apps = db.get_collection("apps")

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

    # Only admin of that app can delete users
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be logged in to an admin account of this app")

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
    sender_email = ""
    receiver_email = ""
    smtp_password = ""

    with open("email_template.html") as f:
        html_template = f.read()

    html_content = html_template.replace("{{code}}", str(auth_code))
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
    new_admin_email: Annotated[str, Form()],
    response: Response,
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    apps = db.get_collection("apps")

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
    # Only admin of that app can transfer ownership
    if logged_in_user.get("app") != app_name:
        raise HTTPException(403, "You must be logged in to an admin account of this app")

    if not apps.find_one({"app_name": app_name}):
        raise HTTPException(404, "App not found")

    new_admin = user_col.find_one({"email": new_admin_email, "app": app_name})
    if not new_admin:
        raise HTTPException(404, "New admin user not found in this app")

    # Update roles
    user_col.update_one(
        {"email": session_data.email},
        {"$set": {"type": "user"}}
    )
    user_col.update_one(
        {"email": new_admin_email},
        {"$set": {"type": "admin"}}
    )

    return {"message": "App ownership transferred successfully"}



@app.get("/admin/dashboard")
async def admin_dashboard(
    request: Request,
    session_id: UUID = Depends(cookie),
    session_data: SessionData = Depends(verifier)
):
    # Ensure admin access
    user = user_col.find_one({"email": session_data.email})
    if not user or user.get("type") != "admin":
        raise HTTPException(403, "Admins only")

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
        "admin_email": session_data.email,
        "app_stats": app_stats
    })
