
import sqlite3

from werkzeug.security import generate_password_hash
from database import get_connection, initialize_database


def create_admin():

    initialize_database()

    print("\n===== ADMINISTRATOR ACCOUNT SETUP =====")

    full_name = input("Enter administrator name: ").strip()
    email = input("Enter administrator email: ").strip().lower()

    if not full_name or not email:
        print("Name and email are required.")
        return

    if len(full_name) > 100 or len(email) > 150:
        print("Name or email is too long.")
        return

    if "@" not in email or "." not in email.split("@")[-1]:
        print("Please enter a valid email address.")
        return

    password = input("Create administrator password: ")
    confirm_password = input("Confirm administrator password: ")

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    if password != confirm_password:
        print("Passwords do not match.")
        return

    password_hash = generate_password_hash(password)

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO users
            (full_name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
            """,
            (full_name, email, password_hash, "admin")
        )

        connection.commit()

        print("\nAdministrator account created successfully!")
        print("Your account role is: admin")

    except sqlite3.IntegrityError:
        print("\nAn account with this email already exists.")

    finally:
        connection.close()


if __name__ == "__main__":
    create_admin()
