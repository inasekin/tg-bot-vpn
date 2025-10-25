import sqlite3
import os

class Database:
    def __init__(self, db_path='data/bot.db'):
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

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vpn_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    private_key TEXT NOT NULL,
                    public_key TEXT NOT NULL,
                    ip_address TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            conn.commit()

    def add_user(self, user_id, username=None, first_name=None):
        """Добавить пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
            conn.commit()

    def get_user(self, user_id):
        """Получить пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_vpn_config(self, user_id, private_key, public_key, ip_address):
        """Добавить VPN конфигурацию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO vpn_configs (user_id, private_key, public_key, ip_address)
                VALUES (?, ?, ?, ?)
            ''', (user_id, private_key, public_key, ip_address))
            conn.commit()
            return cursor.lastrowid

    def get_vpn_config(self, user_id):
        """Получить VPN конфигурацию пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM vpn_configs 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_next_ip(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT ip_address FROM vpn_configs ORDER BY id DESC LIMIT 1')
            row = cursor.fetchone()

            if not row:
                return '10.0.0.2'

            last_ip = row['ip_address']
            parts = last_ip.split('.')
            last_octet = int(parts[3]) + 1

            if last_octet > 254:
                raise Exception("IP адреса закончились")

            return f"10.0.0.{last_octet}"

db = Database()

if __name__ == "__main__":
    print("Тест базы данных...")

    test_user_id = 123456789
    db.add_user(test_user_id, "testuser", "Test User")
    print(f"Пользователь добавлен")

    user = db.get_user(test_user_id)
    print(f"Пользователь: {user}")

    ip = db.get_next_ip()
    print(f"Следующий IP: {ip}")

    db.add_vpn_config(
        test_user_id,
        "test_private_key",
        "test_public_key",
        ip
    )
    print(f"VPN конфиг добавлен")

    config = db.get_vpn_config(test_user_id)
    print(f"VPN конфиг: {config}")