import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME", "sovereign_ai"),
}


def get_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)

        if connection.is_connected():
            return connection

    except Error as e:
        print(f"MySQL connection error: {e}")

    return None


def get_user(username):
    connection = get_connection()

    if not connection:
        return None

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT
                u.id,
                u.username,
                u.role,
                c.name AS company
            FROM users u
            JOIN companies c
                ON u.company_id = c.id
            WHERE u.username = %s
            """,
            (username,)
        )

        return cursor.fetchone()

    except Error as e:
        print(f"MySQL user query error: {e}")
        return None

    finally:
        if cursor:
            cursor.close()

        connection.close()


if __name__ == "__main__":
    print("Testing MySQL user lookup...")

    user = get_user("admin")

    if user:
        print("User found:")
        print(user)
    else:
        print("User not found.")
    