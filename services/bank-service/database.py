import json
import os

DB_FILE = "bank_db.json"

DEFAULT_DB = {
    "accounts": {
        "checking": 5000.0,
        "savings": 1000.0
    }
}

def init_db():
    """Initializes the database file if it does not exist."""
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DB)

def load_db() -> dict:
    """Loads the database state from the JSON file."""
    init_db()
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DB

def save_db(data: dict):
    """Saves the database state to the JSON file."""
    try:
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass

def get_balance(account_name: str) -> float:
    """Gets the balance of an account."""
    db = load_db()
    return db.get("accounts", {}).get(account_name, 0.0)

def update_balances(from_acc: str, to_acc: str, amount: float) -> bool:
    """Performs transfer between accounts if funds are sufficient."""
    db = load_db()
    accounts = db.get("accounts", {})
    if from_acc not in accounts or to_acc not in accounts:
        return False
    if accounts[from_acc] < amount:
        return False
    
    accounts[from_acc] -= amount
    accounts[to_acc] += amount
    save_db(db)
    return True
