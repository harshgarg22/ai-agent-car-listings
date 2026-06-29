import os
import json
import uuid
from typing import List, Dict, Any

# Define persistent storage paths inside your existing data directory
DATA_DIR = "data"
USERS_DB_PATH = os.path.join(DATA_DIR, "users_db.json")
BOOKINGS_DB_PATH = os.path.join(DATA_DIR, "bookings_db.json")

class MemoryManager:
    def __init__(self):
        # ---------------------------------------------------------
        # SHORT-TERM MEMORY (RAM-only, disappears on server restart)
        # ---------------------------------------------------------
        self.active_sessions: Dict[str, List[Any]] = {}
        
        # ---------------------------------------------------------
        # LONG-TERM MEMORY (Loaded from flat JSON files)
        # ---------------------------------------------------------
        self._ensure_db_files()
        self.user_profiles: Dict[str, Dict[str, Any]] = self._load_json(USERS_DB_PATH, default={})
        self.bookings_db: List[Dict[str, str]] = self._load_json(BOOKINGS_DB_PATH, default=[])

    # ==========================================
    # FILE I/O HELPERS
    # ==========================================
    def _ensure_db_files(self):
        """Creates the data directory and blank JSON files if they don't exist."""
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(USERS_DB_PATH):
            self._save_json(USERS_DB_PATH, {})
        if not os.path.exists(BOOKINGS_DB_PATH):
            self._save_json(BOOKINGS_DB_PATH, [])

    def _load_json(self, path: str, default: Any) -> Any:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def _save_json(self, path: str, data: Any):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

    # ==========================================
    # SHORT-TERM MEMORY METHODS (Unchanged)
    # ==========================================
    def get_or_create_session(self, session_id: str = None) -> str:
        if not session_id or session_id not in self.active_sessions:
            session_id = str(uuid.uuid4())
            self.active_sessions[session_id] = []
        return session_id

    def get_session_history(self, session_id: str) -> List[Any]:
        return self.active_sessions.get(session_id, [])

    def save_session_history(self, session_id: str, history: List[Any]):
        self.active_sessions[session_id] = history

    # ==========================================
    # LONG-TERM MEMORY METHODS (Now Persistent)
    # ==========================================
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = {
                "name": None,
                "preferences": [], 
                "liked_cars": []   
            }
            self._save_json(USERS_DB_PATH, self.user_profiles)
        return self.user_profiles[user_id]

    def update_user_name(self, user_id: str, name: str):
        profile = self.get_user_profile(user_id)
        profile["name"] = name
        self._save_json(USERS_DB_PATH, self.user_profiles)
        print(f"[LONG-TERM MEMORY] Saved name for {user_id}: {name}")

    def add_user_preference(self, user_id: str, preference: str):
        profile = self.get_user_profile(user_id)
        if preference not in profile["preferences"]:
            profile["preferences"].append(preference)
            self._save_json(USERS_DB_PATH, self.user_profiles)
            print(f"[LONG-TERM MEMORY] Saved preference for {user_id}: {preference}")

    def save_liked_car(self, user_id: str, car_details: str):
        profile = self.get_user_profile(user_id)
        if car_details not in profile["liked_cars"]:
            profile["liked_cars"].append(car_details)
            self._save_json(USERS_DB_PATH, self.user_profiles)
            print(f"[LONG-TERM MEMORY] Saved liked car for {user_id}: {car_details}")

    # ==========================================
    # BOOKING SYSTEM (Now Persistent)
    # ==========================================
    def create_booking(self, car_details: str, date: str, customer_name: str, phone: str) -> str:
        booking_id = f"DBZ-{str(uuid.uuid4())[:6].upper()}"
        
        booking_record = {
            "booking_id": booking_id,
            "car_details": car_details,
            "date": date,
            "customer_name": customer_name,
            "phone": phone
        }
        self.bookings_db.append(booking_record)
        self._save_json(BOOKINGS_DB_PATH, self.bookings_db)
        
        print(f"\n[SYSTEM LOG] New Persistent Booking Created: {booking_record}")
        return booking_id

memory_manager = MemoryManager()