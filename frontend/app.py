import streamlit as st
import sys
import os

# 1. Path Fix: Ensure Streamlit can find the backend folder
# This allows us to run `streamlit run frontend/app.py` from the root directory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agent import AutomotiveAgent

# 2. Page Configuration
st.set_page_config(
    page_title="Dubizzle Car Concierge",
    page_icon="🚗",
    layout="centered"
)

st.title("🚗 Dubizzle AI Concierge")
st.caption("Your premium AI assistant for finding cars and booking test drives in the UAE.")

# 3. Initialize the Session State
# Streamlit re-runs the entire script on every user interaction. 
# We use st.session_state to persist variables across these re-runs.

if "agent" not in st.session_state:
    # Boot up the Gemini Agent only once per browser session
    st.session_state.agent = AutomotiveAgent()

if "session_id" not in st.session_state:
    # A unique tracker for short-term memory (handled by memory.py)
    st.session_state.session_id = None
    
# Hardcoding a user ID for demonstration purposes (simulating a logged-in user)
user_id = "user_harsh_99"

if "messages" not in st.session_state:
    # The visual chat history shown on the screen
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome to Dubizzle Cars! Are you looking for a specific vehicle today, or do you have a budget in mind?"}
    ]

# 4. Render existing chat history to the screen
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 5. Handle User Input
if prompt := st.chat_input("Ask me about SUVs, budgets, or specific brands..."):
    
    # Immediately render the user's message on the screen
    with st.chat_message("user"):
        st.markdown(prompt)
        
    # Append user message to the visual state
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 6. Fetch the AI Response
    # We display a spinner so the user knows the AI (and database) is "thinking"
    with st.chat_message("assistant"):
        with st.spinner("Searching inventory..."):
            try:
                # Pass the message to our backend engine
                reply, updated_session_id = st.session_state.agent.handle_message(
                    user_message=prompt, 
                    session_id=st.session_state.session_id,
                    user_id=user_id # Feeding in the Long-Term Memory ID
                )
                
                # Ensure we track the active session ID assigned by the backend
                st.session_state.session_id = updated_session_id
                
                # Display the reply
                st.markdown(reply)
                
                # Append assistant message to visual state
                st.session_state.messages.append({"role": "assistant", "content": reply})
                
            except Exception as e:
                # Fallback error handling if API limits are hit or db is missing
                error_msg = f"Sorry, I encountered a system error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})