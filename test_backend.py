
import tempfile
from pathlib import Path

import database
from werkzeug.security import check_password_hash, generate_password_hash

# Use a temporary database so your real project data stays untouched.
temp_folder = tempfile.TemporaryDirectory()
database.DATABASE_PATH = Path(temp_folder.name) / "test_database.db"

from app import app

app.config["TESTING"] = True
database.initialize_database()

# Create a test administrator.
connection = database.get_connection()
connection.execute(
    """
    INSERT INTO users (full_name, email, password_hash, role)
    VALUES (?, ?, ?, ?)
    """,
    (
        "Test Admin",
        "admin@test.com",
        generate_password_hash("AdminPass123"),
        "admin"
    )
)
connection.commit()
connection.close()

def check(name, response, expected):
    if response.status_code != expected:
        raise AssertionError(
            f"FAILED: {name} - Expected {expected}, got "
            f"{response.status_code}: {response.get_data(as_text=True)}"
        )
    print(f"PASSED: {name}")


def get_client():
    client = app.test_client()
    response = client.get("/api/csrf-token")
    return client, response.get_json()["csrf_token"]


def register(client, token, name, email, password, role):
    return client.post(
        "/api/register",
        json={
            "full_name": name,
            "email": email,
            "password": password,
            "role": role
        },
        headers={"X-CSRF-Token": token}
    )


def login(email, password):
    client, token = get_client()
    response = client.post(
        "/api/login",
        json={"email": email, "password": password},
        headers={"X-CSRF-Token": token}
    )

    return client, response


print("\n===== BACKEND SECURITY TESTS =====\n")

# 1. Registration
client, token = get_client()

check(
    "Registration without CSRF token is rejected",
    client.post("/api/register", json={}),
    403
)

check(
    "Seeker registration",
    register(client, token, "Test Seeker", "seeker@test.com",
             "SeekerPass123", "seeker"),
    201
)

check(
    "Owner registration",
    register(client, token, "Test Owner", "owner@test.com",
             "OwnerPass123", "owner"),
    201
)

check(
    "Second owner registration",
    register(client, token, "Other Owner", "owner2@test.com",
             "OwnerPass123", "owner"),
    201
)

check(
    "Duplicate email rejected",
    register(client, token, "Another Seeker", "seeker@test.com",
             "SeekerPass123", "seeker"),
    409
)

check(
    "Public admin registration rejected",
    register(client, token, "Fake Admin", "fake@test.com",
             "AdminPass123", "admin"),
    400
)

# 2. Password hashing
connection = database.get_connection()
user = connection.execute(
    "SELECT password_hash FROM users WHERE email = ?",
    ("seeker@test.com",)
).fetchone()

assert user["password_hash"] != "SeekerPass123"
assert check_password_hash(user["password_hash"], "SeekerPass123")
connection.close()

print("PASSED: Password is securely hashed")

# 3. Login
seeker, response = login("seeker@test.com", "SeekerPass123")
check("Correct login", response, 200)

_, response = login("seeker@test.com", "WrongPassword123")
check("Incorrect password rejected", response, 401)

check("Current user session", seeker.get("/api/me"), 200)

# 4. Role restrictions
seeker_token = seeker.get("/api/csrf-token").get_json()["csrf_token"]

check(
    "Seeker cannot add properties",
    seeker.post(
        "/api/properties",
        json={},
        headers={"X-CSRF-Token": seeker_token}
    ),
    403
)

check(
    "Seeker cannot access admin users",
    seeker.get("/api/admin/users"),
    403
)

# 5. Owner property management
owner, response = login("owner@test.com", "OwnerPass123")
check("Owner login", response, 200)

owner_token = response.get_json()["csrf_token"]
headers = {"X-CSRF-Token": owner_token}

check(
    "Property creation without CSRF token rejected",
    owner.post("/api/properties", json={
        "title": "Test House",
        "description": "A test property",
        "location": "Nairobi",
        "price": 50000
    }),
    403
)

response = owner.post(
    "/api/properties",
    json={
        "title": "Test House",
        "description": "A test property",
        "location": "Nairobi",
        "price": 50000
    },
    headers=headers
)
check("Owner can add property", response, 201)

property_id = response.get_json()["property_id"]

# Another owner must not edit or delete this property.
other_owner, response = login("owner2@test.com", "OwnerPass123")
check("Second owner login", response, 200)

other_headers = {
    "X-CSRF-Token": response.get_json()["csrf_token"]
}

check(
    "Owner cannot edit another owner's property",
    other_owner.put(
        f"/api/properties/{property_id}",
        json={
            "title": "Stolen Listing",
            "description": "Attempted change",
            "location": "Nairobi",
            "price": 100
        },
        headers=other_headers
    ),
    404
)

check(
    "Owner cannot delete another owner's property",
    other_owner.delete(
        f"/api/properties/{property_id}",
        headers=other_headers
    ),
    404
)

# Original owner can edit and delete their own property.
check(
    "Owner can edit own property",
    owner.put(
        f"/api/properties/{property_id}",
        json={
            "title": "Updated House",
            "description": "Updated description",
            "location": "Nairobi",
            "price": 60000
        },
        headers=headers
    ),
    200
)

check(
    "Owner can delete own property",
    owner.delete(
        f"/api/properties/{property_id}",
        headers=headers
    ),
    200
)

# 6. Logout and session
check(
    "Logout",
    owner.post("/api/logout", headers=headers),
    200
)

check(
    "Logged-out user cannot access protected route",
    owner.get("/api/me"),
    401
)

# 7. Admin permissions
admin, response = login("admin@test.com", "AdminPass123")
check("Admin login", response, 200)

check(
    "Admin can view registered users",
    admin.get("/api/admin/users"),
    200
)

print("\n===== ALL BACKEND TESTS PASSED! =====")

temp_folder.cleanup()
