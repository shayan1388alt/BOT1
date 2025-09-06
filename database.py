# database.py
import os
import sqlite3
import time
import json
from typing import Optional, Dict, Any, List

DB_PATH = os.getenv("DB_PATH", "shi.db")

def _connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _column_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())

def _init_db():
    conn = _connect()
    cur = conn.cursor()

    # users
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      user_id INTEGER PRIMARY KEY,
      username TEXT,
      shi_balance REAL DEFAULT 0,
      level INTEGER DEFAULT 1,
      exp INTEGER DEFAULT 0,
      stars_balance INTEGER DEFAULT 0,
      coins INTEGER DEFAULT 0,
      last_daily INTEGER DEFAULT 0,
      banned INTEGER DEFAULT 0
    )
    """)

    # settings (for dynamic rates etc)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
      keyname TEXT PRIMARY KEY,
      value TEXT
    )
    """)

    # items
    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      power INTEGER,
      price_shi REAL
    )
    """)

    # inventory
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
      user_id INTEGER,
      item_id INTEGER,
      qty INTEGER DEFAULT 1,
      PRIMARY KEY (user_id, item_id)
    )
    """)

    # transactions (purchases, payments, admin grants)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      type TEXT,
      amount REAL,
      currency TEXT,
      meta TEXT,
      ts INTEGER
    )
    """)

    # battles log
    cur.execute("""
    CREATE TABLE IF NOT EXISTS battles (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      opponent TEXT,
      win INTEGER,
      reward_shi REAL,
      reward_coins INTEGER,
      ts INTEGER
    )
    """)

    # referrals
    cur.execute("""
    CREATE TABLE IF NOT EXISTS referrals (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      referrer INTEGER,
      referred INTEGER,
      ts INTEGER
    )
    """)

    # guilds
    cur.execute("""
    CREATE TABLE IF NOT EXISTS guilds (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT,
      owner INTEGER,
      created_ts INTEGER
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS guild_members (
      guild_id INTEGER,
      user_id INTEGER,
      joined_ts INTEGER,
      PRIMARY KEY (guild_id, user_id)
    )
    """)

    conn.commit()

    # seed default settings and sample items
    cur.execute("INSERT OR IGNORE INTO settings(keyname, value) VALUES(?,?)", ("STARS_PER_SHI", os.getenv("STARS_PER_SHI","5")))
    cur.execute("INSERT OR IGNORE INTO settings(keyname, value) VALUES(?,?)", ("DAILY_SHI", os.getenv("DAILY_SHI","1")))
    cur.execute("INSERT OR IGNORE INTO settings(keyname, value) VALUES(?,?)", ("DAILY_COINS_MIN", os.getenv("DAILY_COINS_MIN","10")))
    cur.execute("INSERT OR IGNORE INTO settings(keyname, value) VALUES(?,?)", ("DAILY_COINS_MAX", os.getenv("DAILY_COINS_MAX","30")))

    # sample items
    cur.execute("SELECT COUNT(*) AS c FROM items")
    if cur.fetchone()["c"] == 0:
        sample = [
            ("چوب‌دستی نوبر", 2, 0.5),
            ("شمشیر برنزی", 5, 1.2),
            ("زره سبک", 3, 0.9),
        ]
        cur.executemany("INSERT INTO items(name, power, price_shi) VALUES (?,?,?)", sample)

    conn.commit()
    conn.close()

_init_db()

# ----------------- helpers -----------------
def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {k: row[k] for k in row.keys()}

# ----------------- settings -----------------
def get_setting(key: str, default: Optional[str]=None) -> str:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE keyname=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else (default if default is not None else "")

def set_setting(key: str, value: str):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO settings(keyname, value) VALUES(?,?) ON CONFLICT(keyname) DO UPDATE SET value=excluded.value", (key, value))
    conn.commit()
    conn.close()

# ----------------- users -----------------
def register_user(user_id: int, username: Optional[str]=None):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if cur.fetchone() is None:
        cur.execute("INSERT INTO users(user_id, username) VALUES(?,?)", (user_id, username or ""))
        conn.commit()
    else:
        if username:
            cur.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
            conn.commit()
    conn.close()

def get_user_safe(user_id: int) -> Dict[str, Any]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    if row is None:
        # auto-register with defaults
        cur.execute("INSERT INTO users(user_id, username) VALUES (?,?)", (user_id, ""))
        conn.commit()
        cur.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = cur.fetchone()
    d = _row_to_dict(row)
    conn.close()
    return d

# alias for older code
get_user = get_user_safe

def update_shi(user_id: int, delta: float):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET shi_balance = shi_balance + ? WHERE user_id=?", (float(delta), user_id))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (user_id, "shi_update", float(delta), "SHI", "update_shi", int(time.time())))
    conn.commit()
    conn.close()

def set_shi(user_id: int, new_amount: float):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET shi_balance = ? WHERE user_id=?", (float(new_amount), user_id))
    conn.commit()
    conn.close()

def update_stars(user_id: int, delta: float):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET stars_balance = stars_balance + ? WHERE user_id=?", (float(delta), user_id))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (user_id, "stars_update", float(delta), "XTR", "update_stars", int(time.time())))
    conn.commit()
    conn.close()

def add_coins(user_id: int, delta: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = coins + ? WHERE user_id=?", (int(delta), user_id))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (user_id, "coins_add", delta, "COINS", f"add_coins:{delta}", int(time.time())))
    conn.commit()
    conn.close()

def set_coins(user_id: int, newval: int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("UPDATE users SET coins = ? WHERE user_id=?", (int(newval), user_id))
    conn.commit()
    conn.close()

def get_leaderboard(limit: int=10) -> List[Dict[str,Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, shi_balance FROM users ORDER BY shi_balance DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

# ----------------- items / shop -----------------
def get_items() -> List[Dict[str,Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM items ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]

def add_item(name: str, power: int, price_shi: float):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO items(name, power, price_shi) VALUES(?,?,?)", (name, int(power), float(price_shi)))
    conn.commit()
    conn.close()

def buy_item(user_id: int, item_id: int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT price_shi FROM items WHERE id=?", (item_id,))
    r = cur.fetchone()
    if r is None:
        conn.close()
        return False
    price = float(r["price_shi"])
    cur.execute("SELECT shi_balance FROM users WHERE user_id=?", (user_id,))
    u = cur.fetchone()
    if u is None or float(u["shi_balance"]) < price:
        conn.close()
        return False
    # deduct & add to inventory
    cur.execute("UPDATE users SET shi_balance = shi_balance - ? WHERE user_id=?", (price, user_id))
    cur.execute("""
      INSERT INTO inventory(user_id, item_id, qty)
      VALUES(?,?,1)
      ON CONFLICT(user_id, item_id) DO UPDATE SET qty = qty + 1
    """, (user_id, item_id))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (user_id, "buy_item", price, "SHI", f"item_id:{item_id}", int(time.time())))
    conn.commit()
    conn.close()
    return True

# ----------------- battles / coins -> SHI -----------------
def record_battle(user_id:int, opponent:str, win:bool, reward_shi:float, reward_coins:int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO battles(user_id, opponent, win, reward_shi, reward_coins, ts) VALUES(?,?,?,?,?,?)",
                (user_id, opponent, int(win), float(reward_shi), int(reward_coins), int(time.time())))
    conn.commit()
    conn.close()

def coins_to_shi_convert(user_id:int, coins_per_shi:int=100, shi_per_chunk:float=0.01):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT coins FROM users WHERE user_id=?", (user_id,))
    r = cur.fetchone()
    if not r:
        conn.close()
        return 0.0
    coins = int(r["coins"])
    chunks = coins // coins_per_shi
    if chunks <= 0:
        conn.close()
        return 0.0
    shi_to_add = chunks * shi_per_chunk
    remaining = coins % coins_per_shi
    cur.execute("UPDATE users SET coins = ? WHERE user_id=?", (remaining, user_id))
    cur.execute("UPDATE users SET shi_balance = shi_balance + ? WHERE user_id=?", (shi_to_add, user_id))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (user_id, "coins_convert", shi_to_add, "SHI", f"coins->{shi_to_add}", int(time.time())))
    conn.commit()
    conn.close()
    return shi_to_add

# ----------------- referrals -----------------
def add_referral(referrer:int, referred:int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO referrals(referrer, referred, ts) VALUES(?,?,?)", (referrer, referred, int(time.time())))
    cur.execute("INSERT INTO transactions(user_id, type, amount, currency, meta, ts) VALUES(?,?,?,?,?,?)",
                (referrer, "referral_reward", 0.5, "SHI", f"referred:{referred}", int(time.time())))
    cur.execute("UPDATE users SET shi_balance = shi_balance + ? WHERE user_id=?", (0.5, referrer))
    conn.commit()
    conn.close()

# ----------------- guilds -----------------
def create_guild(name:str, owner:int) -> int:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("INSERT INTO guilds(name, owner, created_ts) VALUES(?,?,?)", (name, owner, int(time.time())))
    gid = cur.lastrowid
    cur.execute("INSERT INTO guild_members(guild_id, user_id, joined_ts) VALUES(?,?,?)", (gid, owner, int(time.time())))
    conn.commit()
    conn.close()
    return gid

def join_guild(guild_id:int, user_id:int) -> bool:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM guilds WHERE id=?", (guild_id,))
    if not cur.fetchone():
        conn.close()
        return False
    cur.execute("INSERT OR IGNORE INTO guild_members(guild_id, user_id, joined_ts) VALUES(?,?,?)", (guild_id, user_id, int(time.time())))
    conn.commit()
    conn.close()
    return True

def leave_guild(guild_id:int, user_id:int):
    conn = _connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM guild_members WHERE guild_id=? AND user_id=?", (guild_id, user_id))
    conn.commit()
    conn.close()

# ----------------- admin / reporting -----------------
def get_stats() -> Dict[str, Any]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS users FROM users")
    users = cur.fetchone()["users"]
    cur.execute("SELECT SUM(shi_balance) AS total_shi FROM users")
    total_shi = cur.fetchone()["total_shi"] or 0
    cur.execute("SELECT COUNT(*) AS txs FROM transactions")
    txs = cur.fetchone()["txs"]
    conn.close()
    return {"users": users, "total_shi": total_shi, "transactions": txs}

def get_transactions(limit:int=50) -> List[Dict[str,Any]]:
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]
