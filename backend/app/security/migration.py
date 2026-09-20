"""
Database migration module for Sovereign AI — SIH26117.
Safely and idempotently alters existing tables without deleting data.
"""

import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db import get_connection


def _get_existing_columns(cursor, table_name: str) -> set:
    cursor.execute(f"DESCRIBE `{table_name}`")
    rows = cursor.fetchall()
    return {row["Field"] if isinstance(row, dict) else row[0] for row in rows}


def run_migrations():
    """
    Apply safe, idempotent migrations to existing MySQL tables.
    Preserves all existing tables and data.
    """
    connection = get_connection()
    if not connection:
        print("[Migration] ERROR: Could not connect to MySQL database.")
        return False

    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)

        # ----------------------------------------------------
        # 1. Update `users` table
        # ----------------------------------------------------
        user_cols = _get_existing_columns(cursor, "users")

        alter_users = []
        if "name" not in user_cols:
            alter_users.append("ADD COLUMN `name` VARCHAR(255) NULL AFTER `username`")
        if "mobile" not in user_cols:
            alter_users.append("ADD COLUMN `mobile` VARCHAR(30) NULL AFTER `name`")
        if "status" not in user_cols:
            alter_users.append("ADD COLUMN `status` VARCHAR(30) NOT NULL DEFAULT 'PENDING' AFTER `company_id`")
        if "updated_at" not in user_cols:
            alter_users.append("ADD COLUMN `updated_at` TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP AFTER `created_at`")
        if "approved_at" not in user_cols:
            alter_users.append("ADD COLUMN `approved_at` TIMESTAMP NULL AFTER `updated_at`")
        if "approved_by" not in user_cols:
            alter_users.append("ADD COLUMN `approved_by` VARCHAR(100) NULL AFTER `approved_at`")
        if "deleted_at" not in user_cols:
            alter_users.append("ADD COLUMN `deleted_at` TIMESTAMP NULL AFTER `approved_by`")
        if "deleted_by" not in user_cols:
            alter_users.append("ADD COLUMN `deleted_by` VARCHAR(100) NULL AFTER `deleted_at`")
        if "last_login_at" not in user_cols:
            alter_users.append("ADD COLUMN `last_login_at` TIMESTAMP NULL AFTER `deleted_by`")

        if alter_users:
            alter_sql = f"ALTER TABLE `users` {', '.join(alter_users)}"
            print(f"[Migration] Updating users table: {alter_sql}")
            cursor.execute(alter_sql)
            connection.commit()
            print("[Migration] `users` table successfully updated.")
        else:
            print("[Migration] `users` table is already up to date.")

        # ----------------------------------------------------
        # 2. Bootstrap existing users
        # ----------------------------------------------------
        cursor.execute("""
            UPDATE `users`
            SET
                `status` = 'APPROVED',
                `approved_by` = 'system',
                `approved_at` = COALESCE(`approved_at`, NOW()),
                `name` = CASE
                    WHEN `name` IS NULL OR `name` = '' THEN
                        CASE
                            WHEN `username` = 'admin' THEN 'Administrator'
                            WHEN `username` = 'operator' THEN 'Operator User'
                            WHEN `username` = 'other_user' THEN 'Other Org Admin'
                            ELSE `username`
                        END
                    ELSE `name`
                END
            WHERE `status` IS NULL OR `status` = 'PENDING' OR `status` = ''
        """)
        connection.commit()

        # Specifically guarantee admin, operator, other_user are APPROVED and not deleted
        cursor.execute("""
            UPDATE `users`
            SET `status` = 'APPROVED', `deleted_at` = NULL, `deleted_by` = NULL
            WHERE `username` IN ('admin', 'operator', 'other_user')
        """)
        connection.commit()
        print("[Migration] Existing users bootstrapped with APPROVED status.")

        # ----------------------------------------------------
        # 3. Update `audit_logs` table
        # ----------------------------------------------------
        audit_cols = _get_existing_columns(cursor, "audit_logs")

        alter_audit = []
        if "user_id" not in audit_cols:
            alter_audit.append("ADD COLUMN `user_id` INT NULL AFTER `username`")
        if "target_user_id" not in audit_cols:
            alter_audit.append("ADD COLUMN `target_user_id` INT NULL AFTER `status`")
        if "target_username" not in audit_cols:
            alter_audit.append("ADD COLUMN `target_username` VARCHAR(100) NULL AFTER `target_user_id`")
        if "target_role" not in audit_cols:
            alter_audit.append("ADD COLUMN `target_role` VARCHAR(50) NULL AFTER `target_username`")

        if alter_audit:
            alter_sql = f"ALTER TABLE `audit_logs` {', '.join(alter_audit)}"
            print(f"[Migration] Updating audit_logs table: {alter_sql}")
            cursor.execute(alter_sql)
            connection.commit()
            print("[Migration] `audit_logs` table successfully updated.")
        else:
            print("[Migration] `audit_logs` table is already up to date.")

        # ----------------------------------------------------
        # 4. Create `global_sources` table for Global Mode
        # ----------------------------------------------------
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS `global_sources` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `conversation_id` VARCHAR(100) NOT NULL,
                `username` VARCHAR(100) NOT NULL,
                `company_id` INT NULL,
                `url` VARCHAR(2048) NOT NULL,
                `title` VARCHAR(512) NULL,
                `status` VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `last_fetched_at` TIMESTAMP NULL,
                INDEX `idx_conv` (`conversation_id`),
                INDEX `idx_user` (`username`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        connection.commit()
        print("[Migration] `global_sources` table verified/created.")

        return True

    except Exception as e:
        print(f"[Migration] Error during migration: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()


# Alias for consistency
run_database_migrations = run_migrations


if __name__ == "__main__":
    success = run_migrations()
    print(f"Migration completed with status: {success}")