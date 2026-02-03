URL: https://fastapi-template-app-entxr.ondigitalocean.app/
Docs: https://fastapi-template-app-entxr.ondigitalocean.app/docs

---

## Sizebud Developer/Admin API Documentation

### Base URL

* Production: `https://api.sizebud.com` (adjust if different)

### Authentication model (sessions)

This API uses **cookie-based sessions**.

* On successful login, the server sets a cookie named: `fastapi_session`
* Cookie attributes (current config):

  * `Domain: .sizebud.com`
  * `Secure: true` (HTTPS required)
  * `HttpOnly: true` (not accessible from JS)
  * `SameSite: none` (required for cross-site contexts)
  * `Max-Age: 3600` seconds (1 hour)

**What this means in Swagger /docs**

* Most protected endpoints require your browser to already have the session cookie.
* Best workflow:

  1. Call `/login` in the Swagger UI.
  2. Then call protected endpoints in the same browser session.

---

## Roles & Permissions

Users have a `type` field:

* `user`
* `developer`
* `admin`

### Permission summary

* **Developer**:

  * `/create_app`, `/add_collection`, `/list_collections`, `/apps`, `/update_object`
* **Admin-only**:

Admin only routes require the *session user* to be `admin` **and** requires an `admin_password` form field

  * `/change_user_type`, `/delete_user`, `/transfer_app_ownership`

---

## Common Workflow in FastAPI Docs

### 1) Login (start a session)

**POST** `/login`

Form fields:

* `email` (string)
* `password` (string)

Response:

* `{"message": "Login successful"}`
  Also sets the `fastapi_session` cookie.

If incorrect:

* `401 Incorrect email or password`

---

### 2) Check who you are

**GET** `/me`

Auth:

* Requires valid session cookie

Response:

* `{"email": "<your email>"}`

Errors:

* `401 Not authenticated`
* `401 Invalid or expired session`

---

### 3) Logout (end a session)

**POST** `/logout`

Auth:

* Requires session cookie

Response:

* `{"message": "Logged out"}`

---

# App Management

## Create an app

**POST** `/create_app`

Auth:

* Requires session cookie
* Session user must be `developer`
* Requires `admin_password` (validated against the `"admin"` account)

Form fields:

* `admin_password` (string)
* `app_name` (string)

Behavior:

* Creates an entry in the global `apps` collection
* Adds `app_name` to the developer’s `apps` list
* Creates a new MongoDB database named `app_name`
* Creates a collection `default_collection`

Responses:

* `{"message": "App created successfully"}`

Errors:

* `403 You must be logged in as an developer`
* `401 Incorrect admin password`
* `400 App name already exists`

---

## Delete an app

**POST** `/delete_app`

Auth:

* Requires session cookie
* Session user must be `developer`
* Requires `admin_password`
* Developer must currently be a developer of that app

Form fields:

* `admin_password` (string)
* `app_name` (string)

Behavior:

* Deletes app from the global `apps` collection
* Drops the MongoDB database named `app_name`
* Deletes users in `User_Info` that match `{"apps": app_name}` (⚠️ see note below)

Response:

* `{"message": "App and associated data deleted successfully"}`

Errors:

* `403 You must be logged in as an developer`
* `401 Incorrect admin password`
* `403 You must be a developer of this app`
* `404 App not found`


## List all apps (developer-only)

**GET** `/apps`

Auth:

* Requires session cookie
* Session user must be `developer`

Response shape:

* `{"apps": [ ... ]}` (documents from the `apps` collection, excluding `_id`)

Errors:

* `403 You must be logged in as an developer`

---

## Transfer app ownership

**POST** `/transfer_app_ownership`

Auth:

* Requires session cookie
* Session user must be `developer`
* Requires `admin_password`
* Both current developer and new developer must have the app in their `apps` list (as currently written)

Form fields:

* `admin_password` (string)
* `app_name` (string)
* `new_developer_email` (string)

Behavior:

* Removes `app_name` from current developer’s `apps`
* Adds `app_name` to new developer’s `apps`

Response:

* `{"message": "App ownership transferred successfully"}`

Errors:

* `404 New developer user not found in this app` (means target user doesn’t exist *or* doesn’t currently have `apps: app_name`)

---

# Collection Management (inside an app)

## Add a collection to an app

**POST** `/add_collection`

Auth:

* Requires session cookie
* Session user must be `developer`
* Session user must be a developer of that `app_name`

Form fields:

* `app_name` (string)
* `collection_name` (string)

Behavior:

* Creates MongoDB collection in database `client[app_name]`
* Finds all users in `User_Info` where `apps` includes `app_name`
* Inserts `{ "userId": "<email>" }` into the new collection for each user

Response:

```json
{
  "message": "Collection added and userId objects created successfully",
  "objects_created": 42
}
```

Errors:

* `403 You must be logged in as an developer`
* `403 You must be a developer of this app`
* `404 App not found`
* `400 Collection already exists`

---

## Delete a collection

**POST** `/delete_collection`

Auth:

* Requires session cookie
* Session user must be `developer`
* Must be developer of the app
* Requires `admin_password`

Form fields:

* `admin_password` (string)
* `app_name` (string)
* `collection_name` (string)

Behavior:

* Drops the MongoDB collection

Response:

* `{"message": "Collection deleted successfully"}`

Errors:

* `404 Collection does not exist`
* plus standard permission errors

---

## List collections in an app

**GET** `/list_collections`

Auth:

* Requires session cookie
* Session user must be `developer`
* Must be developer of the app

Query parameters:

* `app_name` (string)

Response:

* `{"collections": ["default_collection", "whatever_else"]}`

---

# User Management

## Delete a user from an app

**POST** `/delete_user`

Auth:

* Requires session cookie
* Session user must be `developer`
* Must be developer of the app
* Requires `admin_password`

Form fields:

* `admin_password` (string)
* `email` (string) – validated by regex
* `app_name` (string)

Behavior:

* Deletes user record matching: `{"email": email, "apps": app_name}`
* For every collection in DB `client[app_name]` except `User_Info`, deletes all documents with `{"userId": email}`

Response:

* `{"message": "User and associated data deleted successfully"}`

Errors:

* `404 User not found`
* `400 Invalid email format`
* `404 App not found`

---

## Change a user type (admin only)

**POST** `/change_user_type`

Auth:

* Requires session cookie
* **Session user must be `admin`**
* Also requires `admin_password`

Form fields:

* `admin_password` (string)
* `target_email` (string)
* `new_type` (string: `admin | user | developer`)
* `app_name` (string)

Behavior:

* Finds user record matching `{"email": target_email, "apps": app_name}`
* Sets `type` to `new_type`

Response:

* `{"message": "User type updated successfully"}`

Errors:

* `403 You must be logged in as an admin`
* `400 Invalid user type`
* `404 Target user not found in this app`

---

# Object Management (per userId)

## Update (merge) a user object in a collection

**POST** `/update_object`

Auth:

* Requires session cookie
* Session user must be `developer`
* Must be developer of the app

Form fields:

* `app_name` (string)
* `collection_name` (string)
* `userId` (string) – usually the user email
* `obj` (string) – JSON string, parsed server-side

Behavior:

* Confirms `{"userId": userId}` exists in `client[app_name][collection_name]`
* Parses `obj` as JSON
* Runs:

  * `collection.update_one({"userId": userId}, {"$set": obj_dict})`

Response:

* `{"message": "Object merged into userId successfully"}`

Errors:

* `400 Invalid JSON in obj`
* `404 UserId not found in collection`
* `404 Collection does not exist`

Example `obj` value:

```json
{"height": 72, "weight": 180, "preferences": {"units": "imperial"}}
```

In Swagger, you must paste it as a string into the `obj` field.

---

# Admin Dashboard (HTML)

## View dashboard

**GET** `/admin/dashboard`

Auth:

* Requires session cookie
* **Developers only** (currently checks `type == developer`)

Returns:

* Server-side rendered HTML template: `dashboard.html`

---

# Public / Utility Endpoints

## Health check

**GET** `/health`

Response:

* `{"status": "ok"}`

## Root route

**GET** `/`

Response:

* Includes list of routes & methods (useful for debugging)

---

# Registration & Password Reset (for end users)

Even though you asked mainly about app/user management, devs will see these in `/docs`, so it helps to document them briefly.

## Register (start email verification)

**POST** `/register`

* Sends a verification code email
* Stores pending record in `email_verification` with 10-minute TTL

Form fields:

* `email`
* `password`
* `app_name`

## Verify email (complete registration)

**POST** `/verify_email`

* Creates user in `User_Info`
* Creates `{userId: email}` in each app collection (except `User_Info`)

Form fields:

* `email`
* `code`

## Reset password (send code)

**POST** `/reset_password`
Form fields:

* `email`

## Confirm reset password

**POST** `/confirm_reset_password`
Form fields:

* `email`
* `code`
* `new_password`

---

# Error Codes & Meanings (quick reference)

* **401 Unauthorized**

  * Not logged in, invalid cookie, or wrong admin password
* **403 Forbidden**

  * Logged in, but lacks role (`developer`/`admin`) or not assigned to that app
* **404 Not Found**

  * App/collection/user/verification record doesn’t exist
* **400 Bad Request**

  * Invalid email format, invalid JSON, invalid user type, etc.

---

# Practical Notes for Swagger UI Users

1. **Use the same browser tab** for `/docs` during your whole session (cookies are tab/browser-based).
2. If you’re calling this API from a frontend:

   * use `credentials: "include"` (fetch) so cookies are sent
3. If cookies aren’t sticking, confirm:

   * you’re on HTTPS
   * `SameSite=None; Secure` is present
   * your frontend domain matches the allowed origins

---
