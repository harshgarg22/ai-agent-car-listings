import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from backend.api import execute_hybrid_search
from backend.memory import memory_manager

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# --- BASE SYSTEM PROMPT ---
# We make this a base template so we can inject the user's memory dynamically later.
BASE_SYSTEM_PROMPT = """
You are the elite AI Car Concierge exclusively for Dubizzle Cars in the UAE. 
Your singular objective is to sell vehicles, assist users with queries, and book test drives.

CRITICAL BEHAVIORAL GUARDRAILS:
1. ANTI-HALLUCINATION: ONLY suggest cars returned by `search_cars_inventory`. Never invent cars.
2. NO COMPETITORS: Politely decline to discuss competitors (Cars24, Dubicars, etc.) and pivot to Dubizzle.
3. PROACTIVE SEARCHING: Always trigger `search_cars_inventory` if a user mentions car preferences.
4. MEMORY MANAGEMENT: If a user states a strong preference (e.g., "I only like white cars", "my budget is 50k"), use the `save_user_preference` tool. If they like a specific car, use `save_liked_car`.
5. BOOKING PROTOCOL: If they want a test drive, you MUST collect their Name, Phone, and Preferred Date/Time before calling `book_test_drive`. Ask for missing info!

FORMATTING:
- Present matching cars natively with clear structure (AED [Price], [Kms] km).
- Ignore any residual marketplace boilerplate text (like "Buy with confidence") from the data when summarizing.
"""

#tool definitions for the llm, each tool internally calls another tool stored in either backend.api or backend.memory

#this is the core function that searches the 
def search_cars_inventory(
    query: str = None, make: str = None, max_price: float = None, 
    min_year: int = None, trim: str = None, max_odometer: float = None,
    has_emi: bool = None, max_emi_monthly: float = None, max_emi_downpayment: float = None
) -> str:
    """
    Queries the Dubizzle vehicle database. ALWAYS use this tool to check inventory before replying.
    
    Args:
        query: Optional descriptive text (e.g., 'leather seats', 'family SUV'). Leave blank/null if the user only gave hard facts like make or price.
        make: The automobile manufacturer brand name (e.g., 'Toyota', 'Nissan', 'Rolls Royce').
        max_price: Maximum vehicle budget constraint in AED.
        min_year: The minimum acceptable manufacturing year threshold (e.g., 2021).
        trim: Specific version tier designation string.
        max_odometer: Absolute maximum allowed distance traveled in kilometers.
        has_emi: Set to True if user explicitly requires finance options.
        max_emi_monthly: Maximum monthly payment budget limit in AED.
        max_emi_downpayment: Maximum upfront downpayment limit in AED.
    """
    results = execute_hybrid_search(
        query=query, make=make, max_price=max_price, min_year=min_year, trim=trim, 
        max_odometer=max_odometer, has_emi=has_emi, max_emi_monthly=max_emi_monthly, 
        max_emi_downpayment=max_emi_downpayment
    )
    if not results:
        return "DATABASE_RESPONSE: No vehicles currently match these criteria."
    return json.dumps(results, indent=2)

def book_test_drive(car_details: str, date: str, customer_name: str, phone: str) -> str:
    """
    Books a test drive. ONLY call this when you have collected the car details, date, name, and phone.
    
    Args:
        car_details: Make, Model, and Year of the car.
        date: Preferred date and time (e.g., 'Saturday at 2 PM').
        customer_name: User's full name.
        phone: User's contact phone number.
    """
    booking_id = memory_manager.create_booking(car_details, date, customer_name, phone)
    return f"SUCCESS: Test drive booked. Booking Reference ID is {booking_id}."

def save_user_preference(user_id: str, preference: str) -> str:
    """
    Saves a user's long-term preference (like budget, color, or preferred car type).
    
    Args:
        user_id: The ID of the current user (provided in your system prompt).
        preference: A clear sentence describing what they want (e.g., 'Prefers white SUVs under 50k').
    """
    memory_manager.add_user_preference(user_id, preference)
    return "SUCCESS: Preference saved to user profile."

def save_liked_car(user_id: str, car_details: str) -> str:
    """
    Bookmarks a specific car that the user showed strong interest in.
    
    Args:
        user_id: The ID of the current user (provided in your system prompt).
        car_details: The Make, Model, Year, and Price of the car they liked.
    """
    memory_manager.save_liked_car(user_id, car_details)
    return "SUCCESS: Car saved to user's liked list."

# ==========================================
# AGENT ORCHESTRATOR
# ==========================================

class AutomotiveAgent:
    def __init__(self):
        # We define the available toolbox here
        self.toolbox = [
            search_cars_inventory, 
            book_test_drive, 
            save_user_preference, 
            save_liked_car
        ]

    def _get_dynamic_model(self, user_id: str):
        """Creates a Gemini model instance infused with the user's long-term memory."""
        # 1. Fetch their long-term profile from memory.py
        profile = memory_manager.get_user_profile(user_id)
        
        # 2. Build the dynamic memory context string
        memory_context = f"\n\n--- CURRENT USER CONTEXT ---\n"
        memory_context += f"USER ID: {user_id} (Pass this exact ID to memory tools if needed)\n"
        memory_context += f"KNOWN PREFERENCES: {profile['preferences'] if profile['preferences'] else 'None yet'}\n"
        memory_context += f"LIKED CARS: {profile['liked_cars'] if profile['liked_cars'] else 'None yet'}\n"
        
        # 3. Combine base rules with dynamic memory
        full_system_prompt = BASE_SYSTEM_PROMPT + memory_context
        
        # 4. Return a freshly configured model
        return genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=full_system_prompt,
            tools=self.toolbox
        )

    def handle_message(self, user_message: str, session_id: str = None, user_id: str = "guest_user"):
        # 1. Prepare short-term memory (Session)
        session_id = memory_manager.get_or_create_session(session_id)
        history = memory_manager.get_session_history(session_id)
        
        # 2. Initialize the AI with long-term memory (Profile)
        model = self._get_dynamic_model(user_id)
        
        # 3. Start chat with existing history
        chat = model.start_chat(
            enable_automatic_function_calling=True,
            history=history
        )
        
        # 4. Send message and get response
        response = chat.send_message(user_message)
        
        # 5. Save the updated chat flow back to short-term memory
        memory_manager.save_session_history(session_id, chat.history)
        
        return response.text, session_id

# --- Verification & Testing ---
if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    agent = AutomotiveAgent()
    my_user_id = "user_harsh_99"
    current_session = None
    
    print("\n================ DAY 1 ================")
    msg1 = "Hi, I'm looking for a reliable SUV under 90,000 AED. I strongly prefer white cars."
    print(f"User: {msg1}")
    reply, current_session = agent.handle_message(msg1, current_session, my_user_id)
    print(f"Agent: {reply}")
    
    msg2 = "I really like that first Nissan you mentioned. Can we book a test drive for it tomorrow at 10 AM? My name is Harsh and my number is 0501234567."
    print(f"\nUser: {msg2}")
    reply, current_session = agent.handle_message(msg2, current_session, my_user_id)
    print(f"Agent: {reply}")
    
    print("\n================ DAY 2 ================")
    print("(User returns the next day. Session ID is lost, but User ID remains!)")
    new_session = None # Simulating a new browser tab
    
    msg3 = "Hi, I'm back. Did I have any cars saved from yesterday?"
    print(f"\nUser: {msg3}")
    reply, new_session = agent.handle_message(msg3, new_session, my_user_id)
    print(f"Agent: {reply}")
    