import sqlite3
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64
import os
from pathlib import Path

class EncryptedTokenManagerDB:
    def __init__(self, db_path="tokens.db", key="key.bin"):
        """
        初始化 Token 管理器
        db_path: SQLite 数据库文件路径
        key: AES 密钥文件路径，若不存在则创建新密钥文件
        """
        self.db_path = db_path
        
        # 将key视为密钥文件路径
        key_path = Path(key)
        
        if not key_path.exists():
            # 如果密钥文件不存在，生成新密钥并保存
            os.makedirs(key_path.parent, exist_ok=True)  # 确保目录存在
            new_key = get_random_bytes(32)  # 生成32字节(256位)密钥
            with open(key_path, 'wb') as f:
                f.write(new_key)
            self.key = new_key
        else:
            # 从文件加载密钥
            with open(key_path, 'rb') as f:
                key_data = f.read()
                # 确保密钥是32字节
                if len(key_data) != 32:
                    # 如果不是32字节，进行调整并覆盖原文件
                    adjusted_key = key_data[:32] if len(key_data) > 32 else key_data + bytes(32 - len(key_data))
                    with open(key_path, 'wb') as f2:
                        f2.write(adjusted_key)
                    self.key = adjusted_key
                else:
                    self.key = key_data
                
        self.init_db()

    def init_db(self):
        """初始化数据库和表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tokens (
                    id TEXT PRIMARY KEY,
                    encrypted_token TEXT NOT NULL
                )
            ''')
            conn.commit()

    def pad(self, data):
        """填充数据到 16 字节倍数"""
        padding_length = 16 - (len(data) % 16)
        return data + bytes([padding_length] * padding_length)

    def unpad(self, data):
        """移除填充"""
        padding_length = data[-1]
        return data[:-padding_length]

    def encrypt_token(self, token):
        """加密 Token"""
        iv = get_random_bytes(16)  # 随机 IV
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded_token = self.pad(token.encode())
        ciphertext = cipher.encrypt(padded_token)
        # 将 IV + 密文编码为 Base64，适合 SQLite 存储
        return base64.b64encode(iv + ciphertext).decode()

    def decrypt_token(self, encrypted_token):
        """解密 Token"""
        encrypted_data = base64.b64decode(encrypted_token)
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded_token = cipher.decrypt(ciphertext)
        return self.unpad(padded_token).decode()

    def add_token(self, id, token):
        """添加或更新 Token（加密存储）"""
        encrypted_token = self.encrypt_token(token)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT OR REPLACE INTO tokens (id, encrypted_token) VALUES (?, ?)', 
                          (id, encrypted_token))
            conn.commit()

    def get_token(self, id):
        """获取 Token（解密返回）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT encrypted_token FROM tokens WHERE id = ?', (id,))
            result = cursor.fetchone()
            return self.decrypt_token(result[0]) if result else None

    def remove_token(self, id):
        """删除 Token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM tokens WHERE id = ?', (id,))
            conn.commit()

    def list_tokens(self):
        """列出所有 Token（解密返回）"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, encrypted_token FROM tokens')
            return {id: self.decrypt_token(enc_token) for id, enc_token in cursor.fetchall()}
