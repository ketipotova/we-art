import streamlit as st
from openai import OpenAI
import time
import qrcode
from io import BytesIO
import base64
from PIL import Image
import requests
import hashlib
import sqlite3
from datetime import datetime
import os
import logging
import extra_streamlit_components as stx
import json

# Cookie Manager setup
def get_cookie_manager():
    return stx.CookieManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database setup
def init_db():
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                api_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        raise

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, password, api_key):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, password_hash, api_key) VALUES (?, ?, ?)",
            (username, hash_password(password), api_key)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('users.db', check_same_thread=False)
    c = conn.cursor()
    try:
        c.execute(
            "SELECT password_hash, api_key FROM users WHERE username = ?",
            (username,)
        )
        result = c.fetchone()
        
        if result and result[0] == hash_password(password):
            api_key = result[1]
            save_session(username, api_key)
            return api_key
        return None
    finally:
        conn.close()

def save_session(username, api_key):
    cookie_manager = get_cookie_manager()
    session_data = {
        'username': username,
        'api_key': api_key,
        'timestamp': str(datetime.now())
    }
    cookie_manager.set('session_data', json.dumps(session_data), expires_at=datetime.now() + datetime.timedelta(days=30))

def load_session():
    try:
        cookie_manager = get_cookie_manager()
        session_data = cookie_manager.get('session_data')
        if session_data:
            data = json.loads(session_data)
            return data.get('username'), data.get('api_key')
    except Exception as e:
        logger.error(f"Session loading error: {str(e)}")
    return None, None

def clear_session():
    try:
        cookie_manager = get_cookie_manager()
        cookie_manager.delete('session_data')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    except Exception as e:
        logger.error(f"Session clearing error: {str(e)}")

# Page Configuration
st.set_page_config(
    page_title="AI სურათების გენერატორი",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'page' not in st.session_state:
    st.session_state.page = 'auth'
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'history' not in st.session_state:
    st.session_state.history = []
if 'username' not in st.session_state:
    st.session_state.username = None

# Global client variable
client = None

def show_auth_page():
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.title("მოგესალმებით! 👋")
    
    tab1, tab2 = st.tabs(["შესვლა", "რეგისტრაცია"])
    
    with tab1:
        with st.form(key="login_form"):
            login_username = st.text_input("მომხმარებელი", key="login_username")
            login_password = st.text_input("პაროლი", type="password", key="login_password")
            login_submitted = st.form_submit_button("შესვლა")
            
            if login_submitted:
                api_key = verify_user(login_username, login_password)
                if api_key:
                    st.session_state.authenticated = True
                    st.session_state.api_key = api_key
                    st.session_state.username = login_username
                    st.session_state.page = 'input'
                    st.rerun()
                else:
                    st.error("არასწორი მომხმარებელი ან პაროლი")

    with tab2:
        with st.form(key="register_form"):
            new_username = st.text_input("მომხმარებელი", key="register_username")
            new_password = st.text_input("პაროლი", type="password", key="register_password")
            confirm_password = st.text_input("გაიმეორეთ პაროლი", type="password", key="confirm_password")
            api_key = st.text_input("OpenAI API გასაღები", type="password", key="api_key_input")
            register_submitted = st.form_submit_button("რეგისტრაცია")
            
            if register_submitted:
                if new_password != confirm_password:
                    st.error("პაროლები არ ემთხვევა")
                elif len(new_password) < 6:
                    st.error("პაროლი უნდა შეიცავდეს მინიმუმ 6 სიმბოლოს")
                elif not api_key.startswith('sk-'):
                    st.error("არასწორი API გასაღები")
                else:
                    if create_user(new_username, new_password, api_key):
                        st.success("რეგისტრაცია წარმატებით დასრულდა! გთხოვთ შეხვიდეთ სისტემაში.")
                    else:
                        st.error("მომხმარებელი უკვე არსებობს")

    st.markdown('</div>', unsafe_allow_html=True)

def display_input_page():
    """Display the input form page"""
    st.markdown('<div class="input-container">', unsafe_allow_html=True)

    # Create two rows with four columns each
    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)

    with row1_col1:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">👤 სახელი</p>', unsafe_allow_html=True)
        name = st.text_input("", placeholder="მაგ: გიორგი", label_visibility="collapsed", key="name_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row1_col2:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🎂 ასაკი</p>', unsafe_allow_html=True)
        age = st.number_input("", min_value=5, max_value=100, value=25, label_visibility="collapsed", key="age_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row1_col3:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🎯 კატეგორია</p>', unsafe_allow_html=True)
        hobby_category = st.selectbox("", list(hobbies.keys()), label_visibility="collapsed", key="category_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row1_col4:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🎨 ჰობი</p>', unsafe_allow_html=True)
        hobby = st.selectbox("", list(hobbies[hobby_category].keys()), label_visibility="collapsed", key="hobby_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row2_col1:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🎨 ფერი</p>', unsafe_allow_html=True)
        color = st.selectbox("", list(colors.keys()), label_visibility="collapsed", key="color_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row2_col2:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🖼️ სტილი</p>', unsafe_allow_html=True)
        style = st.selectbox("", list(styles.keys()), label_visibility="collapsed", key="style_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row2_col3:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">😊 განწყობა</p>', unsafe_allow_html=True)
        mood = st.selectbox("", list(moods.keys()), label_visibility="collapsed", key="mood_input")
        st.markdown('</div>', unsafe_allow_html=True)

    with row2_col4:
        st.markdown('<div class="feature-container">', unsafe_allow_html=True)
        st.markdown('<p class="feature-label">🌈 ფილტრი</p>', unsafe_allow_html=True)
        filter_effect = st.selectbox("", list(filters.keys()), label_visibility="collapsed", key="filter_input")
        st.markdown('</div>', unsafe_allow_html=True)

    # Generate button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✨ შექმენი სურათი", use_container_width=True):
            if not name:
                st.error("გთხოვთ შეიყვანოთ სახელი")
                return

            st.session_state.user_data = {
                "name": name,
                "age": age,
                "hobby_category": hobby_category,
                "hobby": hobby,
                "color": color,
                "style": style,
                "mood": mood,
                "filter": filter_effect
            }
            st.session_state.page = 'generate'
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

def display_generation_page():
    """Display the image generation and result page"""
    st.markdown('<div class="generation-container">', unsafe_allow_html=True)

    with st.spinner("🎨 ვქმნით შენთვის უნიკალურ სურათს..."):
        progress_bar = st.progress(0)
        for i in range(100):
            time.sleep(0.01)
            progress_bar.progress(i + 1)

        english_prompt, georgian_summary = create_personalized_prompt(st.session_state.user_data)
        if english_prompt and georgian_summary:
            st.markdown("#### 🔮 სურათის დეტალები:")
            st.markdown(georgian_summary)

            with st.expander("🔍 სრული აღწერა"):
                st.markdown(f"*{english_prompt}*")

            image_url = generate_dalle_image(english_prompt)
            if image_url:
                add_to_history(image_url, english_prompt)

                st.success("✨ თქვენი სურათი მზადაა!")
                st.image(image_url, caption="შენი პერსონალური AI სურათი", use_column_width=True)

                qr_col1, qr_col2 = st.columns([1, 2])
                with qr_col1:
                    st.markdown('<div class="qr-container">', unsafe_allow_html=True)
                    qr_code = create_qr_code(image_url)
                    if qr_code:
                        st.image(qr_code, width=200)
                        st.markdown("📱 დაასკანერე QR კოდი")
                    st.markdown('</div>', unsafe_allow_html=True)

                with qr_col2:
                    st.markdown('<div class="instructions-container">', unsafe_allow_html=True)
                    st.markdown("""
                        ### 📱 როგორ გადმოვწერო:
                        1. გახსენი ტელეფონის კამერა
                        2. დაასკანერე QR კოდი
                        3. გადმოწერე სურათი
                    """)
                    st.markdown('</div>', unsafe_allow_html=True)

                # Download and new image buttons
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(
                        f'<a href="{image_url}" download="ai_image.png" '
                        f'target="_blank"><button style="width:100%">📥 გადმოწერა</button></a>',
                        unsafe_allow_html=True
                    )
                with col2:
                    if st.button("🔄 ახალი სურათი"):
                        st.session_state.page = 'input'
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def show_user_header():
    """Display user header with logout button"""
    if st.session_state.get('authenticated', False):
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🚪 გასვლა", key="logout_button"):
                logout()
        with col1:
            st.markdown(
                f'<div class="user-info"><span>👤 {st.session_state.username}</span></div>',
                unsafe_allow_html=True
            )

def main():
    """Main application function"""
    try:
        # Initialize session state
        init_session()
        
        # Title and subtitle
        st.markdown(
            '<div class="header">',
            unsafe_allow_html=True
        )
        st.title("🎨 AI სურათების გენერატორი")
        st.markdown("### შექმენი შენი უნიკალური სურათი")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Show user header if authenticated
        show_user_header()

        # Display appropriate page based on state
        if not st.session_state.get('authenticated', False):
            show_auth_page()
        else:
            try:
                global client
                client = OpenAI(api_key=st.session_state.api_key)
                
                if st.session_state.get('page', 'input') == 'input':
                    display_input_page()
                    show_history()
                else:
                    display_generation_page()
            except Exception as e:
                st.error(f"API შეცდომა: {str(e)}")
                logout()
                if st.button("🔄 ხელახლა შესვლა"):
                    st.rerun()

        # Footer
        st.markdown(
            """
            <div style='text-align: center; color: rgba(255,255,255,0.5); 
                 padding: 1rem 0; font-size: 0.8rem; margin-top: 2rem;'>
            შექმნილია ❤️-ით DALL-E 3-ის გამოყენებით
            </div>
            """,
            unsafe_allow_html=True
        )

    except Exception as e:
        show_error_message(e)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        st.error(f"კრიტიკული შეცდომა: {str(e)}")
        if st.button("🔄 გვერდის განახლება", key="refresh_button"):
            st.rerun()
