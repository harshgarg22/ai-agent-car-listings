import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
from backend.api import execute_hybrid_search

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# prompt w guard rails in place
SYSTEM_PROMPT = """
You are the elite AI Car Concierge exclusively for Dubizzle Cars in the UAE. 
Your singular objective is to sell vehicles from our database and assist users with automotive queries.

CRITICAL BEHAVIORAL GUARDRAILS:
1. ANTI-HALLUCINATION: You must ONLY suggest cars that are returned by the `search_cars_inventory` tool. Never invent, hallucinate, or assume a car exists.
2. NO COMPETITORS: If the user mentions or asks about competitors (e.g., Cars24, Dubicars, YallaMotor, CarSwitch, SellAnyCar, Automall), you must politely decline to discuss them and immediately pivot the conversation back to Dubizzle's premium inventory.
3. OFF-TOPIC FIREWALL: You are strictly an automotive AI. If the user asks about coding, recipes, politics, or any non-automotive topic, reply: "I am a Dubizzle automotive concierge. I can only assist you with finding and purchasing vehicles. How can I help you find your next car?"
4. PROACTIVE SEARCHING: Even if the user only types a single word (like "Toyota" or "SUV"), you MUST immediately trigger the `search_cars_inventory` tool to find matches before replying. Do not ask for permission to search.

FORMATTING:
- Present matching cars natively with clear structure. Format prices as "AED [Price]" and odometer as "[Kms] km".
- Ignore any residual marketplace boilerplate text (like "Buy with confidence") from the data when summarizing.
"""

#so this func has the same signature as the one in backend.api as it internally calls that
#this func will serve as the main func for tool calling
#gemini will only read the docstring and typehints only thats why its so detailed 
def search_cars_inventory(
    query: str = None, 
    make: str = None, 
    max_price: float = None, 
    min_year: int = None,
    trim: str = None,
    max_odometer: float = None,
    has_emi: bool = None,
    max_emi_monthly: float = None,
    max_emi_downpayment: float = None
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
        query=query,
        make=make,
        max_price=max_price,
        min_year=min_year,
        trim=trim,
        max_odometer=max_odometer,
        has_emi=has_emi,
        max_emi_monthly=max_emi_monthly,
        max_emi_downpayment=max_emi_downpayment
    )
    
    if not results:
        return "DATABASE_RESPONSE: No vehicles currently match these criteria in the active Dubizzle inventory."
        
    return json.dumps(results, indent=2)

#this is the main function, for now i am calling gemini 2.5 flash, might change depending on limits
#takes in the system prompt and the func for tool calling
class AutomotiveAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT,
            tools=[search_cars_inventory]
        )

    def handle_message(self, user_message: str, history=None):
        chat = self.model.start_chat(enable_automatic_function_calling=True)
        if history:
            chat.history = history
        response = chat.send_message(user_message)
        return response.text

if __name__ == "__main__":
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    print("Initializing Guardrailed Dubizzle Agent...")
    agent = AutomotiveAgent()
    
    # simple tests for the guardrails, u can add whatever you want here
    tests = [
        "Find me a Rolls royce"
    ]
    
    for t in tests:
        print(f"\nUser: {t}")
        reply = agent.handle_message(t)
        print(f"Agent response:\n{reply}")
        print("-" * 40)