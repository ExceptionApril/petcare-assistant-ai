import streamlit as st
import google.generativeai as genai
import os
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="PetCare Assistant AI",
    page_icon="🐾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stTextInput > div > div > input {
        font-size: 16px;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    .chat-message.user {
        background-color: #e3f2fd;
    }
    .chat-message.assistant {
        background-color: #f5f5f5;
    }
    .chat-message .message {
        padding: 0;
        color: #000;
    }
    h1 {
        color: #1976d2;
    }
    .sidebar-info {
        background-color: #fff3e0;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'api_key' not in st.session_state:
    st.session_state.api_key = ""

if 'model' not in st.session_state:
    st.session_state.model = None

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/color/96/000000/pet-commands-train.png", width=100)
    st.title("🐾 PetCare AI")
    st.markdown("---")
    
    st.markdown("""
    <div class="sidebar-info">
        <h3>About</h3>
        <p>Your AI-powered pet care assistant for:</p>
        <ul>
            <li>🏥 Health advice</li>
            <li>🍔 Nutrition guidance</li>
            <li>🎾 Behavior tips</li>
            <li>💊 Medication info</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # API Key input
    st.markdown("### 🔑 API Configuration")
    api_key_input = st.text_input(
        "Google Gemini API Key",
        type="password",
        value=st.session_state.api_key,
        help="Get your free API key from https://makersuite.google.com/app/apikey"
    )
    
    if api_key_input != st.session_state.api_key:
        st.session_state.api_key = api_key_input
        if api_key_input:
            try:
                genai.configure(api_key=api_key_input)
                st.session_state.model = genai.GenerativeModel('gemini-pro')
                st.success("✅ API key configured!")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
    
    st.markdown("---")
    
    # Pet type selector
    st.markdown("### 🐕 Pet Information")
    pet_type = st.selectbox(
        "Select your pet type",
        ["Dog", "Cat", "Bird", "Rabbit", "Hamster", "Fish", "Other"]
    )
    
    pet_age = st.selectbox(
        "Pet age group",
        ["Puppy/Kitten", "Young", "Adult", "Senior"]
    )
    
    st.markdown("---")
    
    # Clear chat button
    if st.button("🗑️ Clear Chat History"):
        st.session_state.chat_history = []
        st.rerun()
    
    st.markdown("---")
    st.markdown("""
    <small>
    <b>Note:</b> This is an AI assistant. Always consult a veterinarian for serious health concerns.
    </small>
    """, unsafe_allow_html=True)

# Main content
st.title("🐾 PetCare Assistant AI")
st.markdown("### Your AI-powered companion for pet care advice")

# Display API key status
if not st.session_state.api_key:
    st.warning("⚠️ Please enter your Google Gemini API key in the sidebar to start chatting.")
    st.info("""
    **How to get your free API key:**
    1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
    2. Sign in with your Google account
    3. Click "Create API Key"
    4. Copy and paste it in the sidebar
    """)
else:
    st.success("✅ API configured - Ready to chat!")

# Display chat history
for message in st.session_state.chat_history:
    role = message["role"]
    content = message["content"]
    timestamp = message.get("timestamp", "")
    
    if role == "user":
        st.markdown(f"""
        <div class="chat-message user">
            <div style="font-weight: bold; margin-bottom: 0.5rem;">🧑 You {timestamp}</div>
            <div class="message">{content}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="chat-message assistant">
            <div style="font-weight: bold; margin-bottom: 0.5rem;">🐾 PetCare AI {timestamp}</div>
            <div class="message">{content}</div>
        </div>
        """, unsafe_allow_html=True)

# Chat input
st.markdown("---")
col1, col2 = st.columns([5, 1])

with col1:
    user_input = st.text_input(
        "Ask me anything about pet care:",
        placeholder="e.g., What should I feed my senior dog?",
        key="user_input",
        label_visibility="collapsed"
    )

with col2:
    send_button = st.button("Send 📤", use_container_width=True)

# Quick prompts
st.markdown("**Quick prompts:**")
quick_prompts_col1, quick_prompts_col2, quick_prompts_col3, quick_prompts_col4 = st.columns(4)

with quick_prompts_col1:
    if st.button("🏥 Health Tips"):
        user_input = f"What are some general health tips for a {pet_age} {pet_type.lower()}?"
        send_button = True

with quick_prompts_col2:
    if st.button("🍔 Nutrition"):
        user_input = f"What should I feed my {pet_age} {pet_type.lower()}?"
        send_button = True

with quick_prompts_col3:
    if st.button("🎾 Behavior"):
        user_input = f"How can I train my {pet_age} {pet_type.lower()}?"
        send_button = True

with quick_prompts_col4:
    if st.button("💊 Medication"):
        user_input = f"What vaccinations does my {pet_age} {pet_type.lower()} need?"
        send_button = True

# Process user input
if (send_button or user_input) and user_input:
    if not st.session_state.api_key:
        st.error("❌ Please enter your API key in the sidebar first!")
    else:
        # Add user message to history
        timestamp = datetime.now().strftime("%H:%M")
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_input,
            "timestamp": timestamp
        })
        
        # Generate response
        try:
            with st.spinner("🤔 Thinking..."):
                # Create a pet-care focused prompt
                system_context = f"""You are a knowledgeable and friendly pet care assistant. 
                The user has a {pet_age} {pet_type.lower()}.
                Provide helpful, accurate, and compassionate advice about pet care.
                Always remind users to consult a veterinarian for serious health concerns.
                Keep responses concise but informative.
                """
                
                full_prompt = f"{system_context}\n\nUser question: {user_input}"
                
                if st.session_state.model:
                    response = st.session_state.model.generate_content(full_prompt)
                    ai_response = response.text
                else:
                    ai_response = "Error: Model not initialized. Please check your API key."
                
                # Add AI response to history
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": ai_response,
                    "timestamp": timestamp
                })
                
                # Rerun to display new messages
                st.rerun()
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.info("Please check your API key and try again.")

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p><b>PetCare Assistant AI</b> - Midterm Project Progress | Built with Streamlit & Google Gemini</p>
    <p><small>⚠️ Disclaimer: This AI assistant provides general information only. Always consult a licensed veterinarian for medical advice.</small></p>
</div>
""", unsafe_allow_html=True)
