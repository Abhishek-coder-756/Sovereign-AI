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


def get_users():
    connection = get_connection()

    if not connection:
        return []

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                u.id,
                u.username,
                u.role,
                c.name AS company
            FROM users u
            JOIN companies c
                ON u.company_id = c.id
            ORDER BY u.id
        """)

        return cursor.fetchall()

    except Error as e:
        print(f"Query error: {e}")
        return []

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()


if __name__ == "__main__":

    print("========================================")
    print("MYSQL TEST")
    print("========================================")

    users = get_users()

    print("\nUsers in database:")

    for user in users:
        print(
            f"{user['username']} | "
            f"{user['role']} | "
            f"{user['company']}"
        )

    print("\n========================================")