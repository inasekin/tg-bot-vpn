import sqlite3
import os


class Database:
    def __init__(self, db_path="data/bot.db"):
        self.db_path = db_path

        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS vpn_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT NOT NULL,
                    private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    server TEXT NOT NULL DEFAULT 'ru',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, name)
                )
            """
            )

            # Миграция для баз, созданных до появления мультисерверности:
            # добавляем колонку server, если её ещё нет.
            cursor.execute("PRAGMA table_info(vpn_configs)")
            columns = [row[1] for row in cursor.fetchall()]
            if "server" not in columns:
                cursor.execute(
                    "ALTER TABLE vpn_configs ADD COLUMN server TEXT NOT NULL DEFAULT 'ru'"
                )

            conn.commit()

    def add_user(self, user_id, username=None, first_name=None):
        """Добавить пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """,
                (user_id, username, first_name),
            )
            conn.commit()

    def get_user(self, user_id):
        """Получить пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_vpn_config(self, user_id, name, private_key, public_key, ip_address, server="ru"):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO vpn_configs (user_id, name, private_key, public_key, ip_address, server)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (user_id, name, private_key, public_key, ip_address, server),
            )
            conn.commit()
            return cursor.lastrowid

    def get_vpn_config(self, user_id, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM vpn_configs
                WHERE user_id = ? AND name = ?
            """,
                (user_id, name),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_vpn_configs(self, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM vpn_configs
                WHERE user_id = ?
                ORDER BY created_at DESC
            """,
                (user_id,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_vpn_config_by_id(self, config_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM vpn_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def delete_vpn_config(self, user_id, name):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM vpn_configs
                WHERE user_id = ? AND name = ?
            """,
                (user_id, name),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_vpn_config_by_id(self, config_id, user_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM vpn_configs WHERE id = ? AND user_id = ?",
                (config_id, user_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_next_ip(self, server="ru", subnet_prefix="10.0.0."):
        """
        Возвращает следующий свободный IP в подсети конкретного сервера.

        Args:
            server: ключ сервера ("ru", "us", ...)
            subnet_prefix: префикс подсети этого сервера, например "10.0.0." или "10.0.1."
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ip_address FROM vpn_configs
                WHERE server = ?
                ORDER BY id DESC LIMIT 1
            """,
                (server,),
            )
            row = cursor.fetchone()

            if not row:
                return f"{subnet_prefix}2"

            last_ip = row["ip_address"]
            parts = last_ip.split(".")
            last_octet = int(parts[3]) + 1

            if last_octet > 254:
                raise Exception(f"IP адреса на сервере '{server}' закончились")

            return f"{subnet_prefix}{last_octet}"


db = Database()
