# FastAPI App Management API

## Overview
This API allows management of users, applications, and collections in MongoDB.  
It supports user registration, login/logout, app creation, collection management, object updates, and deletion of users/apps.

**Tech Stack:**  
- **Backend:** FastAPI  
- **Database:** MongoDB  
- **Authentication:** Session cookies (`fastapi_sessions`)  
- **Password hashing:** `pwdlib`  

---

## Authentication
- All sensitive routes require **admin login**.
- Authentication is done via **session cookies**.
- `SessionCookie` is attached after `/login` and verified by `BasicVerifier`.

---

## Models

### User
```json
{
  "email": "string",
  "disabled": "boolean"
}
UserInDB
json
Copy code
{
  "email": "string",
  "disabled": "boolean",
  "hashed_password": "string"
}
SessionData
json
Copy code
{
  "email": "string"
}
Endpoints
1. Root
GET /
Returns all routes and a simple message.

Response:

json
Copy code
{
  "message": "API is running",
  "routes": [{"path": "/register", "methods": ["POST"]}, ...]
}
2. Register User
POST /register

Registers a new user for a given app.

Parameters (form):

email – User email

password – Password for account

app_name – App to associate user with

account_type – "admin" or "user"

admin_password – Required if creating an admin

Response:

json
Copy code
{
  "message": "User registered successfully"
}
Notes:

Admin registration requires verification with root admin credentials.

Creates entries in all collections of the app.

3. Login
POST /login

Logs in a user and sets session cookie.

Parameters (form):

email

password

Response:

json
Copy code
{
  "message": "Login successful"
}
4. Logout
POST /logout

Deletes the session and removes the cookie.

Response:

json
Copy code
{
  "message": "Logged out successfully"
}
5. Get Current User
GET /me

Returns details of the logged-in user.

Response:

json
Copy code
{
  "email": "user@example.com",
  "type": "admin"
}
6. Create App
POST /create_app

Creates a new app with optional default collection.

Parameters (form):

app_name – Name of the app

admin_password – Root admin password

Response:

json
Copy code
{
  "message": "App created successfully"
}
7. Add Collection
POST /add_collection

Creates a collection in an app and adds default userId objects.

Parameters (form):

app_name

collection_name

Response:

json
Copy code
{
  "message": "Collection added and userId objects created successfully",
  "objects_created": 5
}
8. Delete Collection
POST /delete_collection

Deletes a collection from an app.

Parameters (form):

app_name

collection_name

admin_password

Response:

json
Copy code
{
  "message": "Collection deleted successfully"
}
9. List Collections
GET /list_collections?app_name=<app_name>

Lists all collections in the app.

Response:

json
Copy code
{
  "collections": ["default_collection", "orders", "products"]
}
10. List Apps
GET /apps

Lists all apps for which the admin has access.

Response:

json
Copy code
{
  "apps": [
    {"app_name": "App1", "created_by": "admin@example.com"},
    {"app_name": "App2", "created_by": "admin@example.com"}
  ]
}
11. Add/Update Object
POST /object

Adds or updates an object for a userId in a collection.

Parameters (form):

app_name

collection_name

userId

obj – JSON string of data

Response:

json
Copy code
{
  "message": "Object merged into userId successfully"
}
12. Delete App
POST /delete_app

Deletes an app, all its collections, and associated users.

Parameters (form):

app_name

admin_password

Response:

json
Copy code
{
  "message": "App and associated data deleted successfully"
}
13. Delete User
POST /delete_user

Deletes a user and their data from all collections in an app.

Parameters (form):

email

app_name

admin_password

Response:

json
Copy code
{
  "message": "User and associated data deleted successfully"
}
Security Notes
Admin password verification is required for sensitive actions.

Only root/admin users can create or delete apps/collections/users.

Sessions use HttpOnly cookies with SameSite=lax for protection.

Example curl Requests
Login Example:

bash
Copy code
curl -X POST http://localhost:8000/login \
  -F "email=admin@example.com" \
  -F "password=adminpass"
Create App Example:

bash
Copy code
curl -X POST http://localhost:8000/create_app \
  -F "app_name=MyApp" \
  -F "admin_password=supersecret"
pgsql
Copy code

---

If you want, I can also **add a table of all endpoints with parameters, types, and auth requirements**, which will make it **look like professional API reference docs** for GitHub. This is ideal for a clean README.  

Do you want me to do that next?
