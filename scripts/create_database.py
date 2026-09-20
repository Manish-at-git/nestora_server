"""Manual utility that creates only the configured new empty MySQL database; it never runs automatically."""

import re

import pymysql

from app.core.config import get_settings


def main() -> None:
    """Connect without selecting a database, validate its name, and create it with utf8mb4 support."""
    settings = get_settings()
    if not re.fullmatch(r"[A-Za-z0-9_]+", settings.mysql_database):
        raise ValueError("MYSQL_DATABASE may contain only letters, numbers, and underscores")
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        charset="utf8mb4",
        autocommit=True,
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
            )
    finally:
        connection.close()
    print(f"Database '{settings.mysql_database}' is ready. Next run: alembic upgrade head")


if __name__ == "__main__":
    main()
