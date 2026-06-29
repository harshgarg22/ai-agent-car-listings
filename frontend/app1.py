import streamlit as st
import requests

# 1. Page Configuration
st.set_page_config(
    page_title="Dubizzle Car Concierge",
    page_icon="🚗",
    layout="centered"
)

st.title("🚗 Dubizzle AI Concierge")
st.caption("Your premium AI assistant for finding cars and booking test drives in the UAE.")

# 2. Configuration for FastAPI backend
API_URL = "http://localhost:8000/api/chat"

# Sidebar for User Profile (Long-Term Memory hook)
with st.sidebar:
    st.header("User Settings")
    user_id = st.text_input("Enter User ID", value="user_harsh_99")
    st.caption("Changing this simulates logging in as a different user.")

# 3. Initialize the Session State
if "session_id" not in st.session_state:
    st.session_state.session_id = None
    
if "messages" not in st.session_state:
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
        
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 6. Fetch the AI Response via FastAPI (HTTP Request)
    with st.chat_message("assistant"):
        with st.spinner("Searching inventory..."):
            
            payload = {
                "message": prompt,
                "session_id": st.session_state.session_id,
                "user_id": user_id 
            }
            
            try:
                # Send the request to FastAPI
                response = requests.post(API_URL, json=payload)
                response.raise_for_status() 
                
                data = response.json()
                reply = data.get("reply")
                
                # Update session ID from backend
                st.session_state.session_id = data.get("session_id")
                
                # Display the reply
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
                
            except requests.exceptions.ConnectionError:
                error_msg = "⚠️ Cannot connect to the FastAPI backend. Make sure it is running on port 8000!"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            except Exception as e:
                error_msg = f"Sorry, I encountered a system error: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})