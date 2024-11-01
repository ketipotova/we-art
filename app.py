# Part 1: Imports and Initial Setup
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
from datetime import datetime, timedelta  # Updated import
import os
import logging
import extra_streamlit_components as stx
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Error handling functions
def show_error_message(error, show_retry=True):
    """Display error message with optional retry button"""
    error_container = st.empty()
    with error_container.container():
        st.error(f"შეცდომა: {str(error)}")
        if show_retry:
            if st.button("🔄 ხელახლა ცდა", key="retry_button", type="primary"):
                st.rerun()

def handle_error(func):
    """Decorator for handling function errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            show_error_message(e)
            return None
    return wrapper

# Cookie Manager setup
def get_cookie_manager():
    return stx.CookieManager()

# Database setup
@handle_error
def init_db():
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

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@handle_error
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

@handle_error
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

# Part 2: Session Management and Configuration

@handle_error
def save_session(username, api_key):
    cookie_manager = get_cookie_manager()
    session_data = {
        'username': username,
        'api_key': api_key,
        'timestamp': str(datetime.now())
    }
    cookie_manager.set('session_data', json.dumps(session_data), 
                      expires_at=datetime.now() + timedelta(days=30))

@handle_error
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

@handle_error
def clear_session():
    try:
        cookie_manager = get_cookie_manager()
        cookie_manager.delete('session_data')
        for key in list(st.session_state.keys()):
            del st.session_state[key]
    except Exception as e:
        logger.error(f"Session clearing error: {str(e)}")

# Initialize the database
init_db()

# Page Configuration
st.set_page_config(
    page_title="AI სურათების გენერატორი",
    page_icon="🎨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Initialize session state
def init_session_state():
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
    if 'error' not in st.session_state:
        st.session_state.error = None
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False

# Global client variable
client = None

# Data structures
hobbies = {
    "სპორტი": {
        "ფეხბურთი": "football",
        "კალათბურთი": "basketball",
        "ჭადრაკი": "chess",
        "ცურვა": "swimming",
        "იოგა": "yoga",
        "ჩოგბურთი": "tennis",
        "სირბილი": "running"
    },
    "ხელოვნება": {
        "ხატვა": "painting",
        "მუსიკა": "music",
        "ცეკვა": "dancing",
        "ფოტოგრაფია": "photography",
        "კერამიკა": "ceramics",
        "ქარგვა": "embroidery"
    },
    "ტექნოლოგია": {
        "პროგრამირება": "programming",
        "გეიმინგი": "gaming",
        "რობოტიკა": "robotics",
        "3D მოდელირება": "3D modeling",
        "AI": "artificial intelligence"
    },
    "ბუნება": {
        "მებაღეობა": "gardening",
        "ლაშქრობა": "hiking",
        "კემპინგი": "camping",
        "ალპინიზმი": "mountain climbing"
    }
}

colors = {
    "წითელი": "red",
    "ლურჯი": "blue",
    "მწვანე": "green",
    "ყვითელი": "yellow",
    "იისფერი": "purple",
    "ოქროსფერი": "gold",
    "ვერცხლისფერი": "silver",
    "ცისფერი": "light blue"
}

styles = {
    "რეალისტური": "realistic",
    "ფანტასტიკური": "fantastic",
    "მულტიპლიკაციური": "cartoon",
    "ანიმე": "anime",
    "იმპრესიონისტული": "impressionistic"
}

moods = {
    "მხიარული": "cheerful",
    "მშვიდი": "peaceful",
    "ენერგიული": "energetic",
    "რომანტიული": "romantic",
    "სათავგადასავლო": "adventurous",
    "ნოსტალგიური": "nostalgic"
}

filters = {
    "ბუნებრივი": "natural",
    "რეტრო": "retro",
    "დრამატული": "dramatic",
    "ნათელი": "bright",
    "კონტრასტული": "high contrast"
}

# Part 3: Authentication and Core UI Components

# Custom styling
st.markdown("""
    <style>
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Remove empty frames by hiding the block-container padding */
    .block-container {
        max-width: 1000px !important;
        padding: 0 !important;
        margin: 0 auto !important;
    }

    /* Hide all empty containers */
    .stContainer:empty,
    .block-container:empty,
    .input-container:empty,
    .generation-container:empty,
    .feature-container:empty {
        display: none;
    }

    /* Base theme */
    .stApp {
        background: linear-gradient(150deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        margin-top: 1rem;
    }

    /* Container styling */
    .input-container, .generation-container {
        background: rgba(255, 255, 255, 0.05);
        padding: 2rem;
        border-radius: 20px;
        backdrop-filter: blur(10px);
        margin: 1rem auto;
        max-width: 900px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Auth container */
    .auth-container {
        background: rgba(255, 255, 255, 0.05);
        padding: 2rem;
        border-radius: 20px;
        backdrop-filter: blur(10px);
        margin: 2rem auto;
        max-width: 500px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    /* Feature container */
    .feature-container {
        background: rgba(255, 255, 255, 0.08);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1rem;
    }

    /* Input styling */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.07);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 0.75rem 1rem;
    }

    /* Select box styling */
    .stSelectbox > div > div {
        background: rgba(255, 255, 255, 0.07);
        border-radius: 10px;
        color: white !important;
    }

    /* Button styling */
    .stButton > button {
        background: linear-gradient(45deg, #FF9A9E, #FAD0C4);
        color: #1a1a2e;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s ease;
    }

    /* Form submit button styling */
    .stFormSubmitter > button {
        background: linear-gradient(45deg, #FF9A9E, #FAD0C4);
        color: #1a1a2e;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        font-weight: bold;
        width: 100%;
        transition: all 0.3s ease;
    }

    /* User info styling */
    .user-info {
        position: fixed;
        top: 1rem;
        right: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        z-index: 999;
        background: rgba(26, 26, 46, 0.8);
        padding: 0.5rem 1rem !important;
        border-radius: 20px;
        backdrop-filter: blur(10px);
    }

    .user-info span {
        color: rgba(255, 255, 255, 0.8);
        font-size: 0.9rem;
    }

    /* QR container */
    .qr-container {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        margin: 1rem auto;
        max-width: 250px;
    }

    /* Instructions container */
    .instructions-container {
        background: rgba(255, 255, 255, 0.08);
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem auto;
    }

    /* Download button styling */
    .download-button {
        display: inline-block;
        background: linear-gradient(45deg, #FF9A9E, #FAD0C4);
        color: #1a1a2e;
        text-decoration: none;
        padding: 0.75rem 2rem;
        border-radius: 10px;
        font-weight: bold;
        width: 100%;
        text-align: center;
        transition: all 0.3s ease;
    }
    
    .download-button:hover {
        opacity: 0.9;
        color: #1a1a2e;
        text-decoration: none;
    }
    </style>
""", unsafe_allow_html=True)

@handle_error
def show_auth_page():
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.title("მოგესალმებით! 👋")
    
    tab1, tab2 = st.tabs(["შესვლა", "რეგისტრაცია"])
    
    with tab1:
        with st.form("login_form"):
            login_username = st.text_input("მომხმარებელი", key="login_username")
            login_password = st.text_input("პაროლი", type="password", key="login_password")
            submit_login = st.form_submit_button("შესვლა")
            
            if submit_login:
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
        with st.form("register_form"):
            new_username = st.text_input("მომხმარებელი", key="register_username")
            new_password = st.text_input("პაროლი", type="password", key="register_password")
            confirm_password = st.text_input("გაიმეორეთ პაროლი", type="password", key="confirm_password")
            api_key = st.text_input("OpenAI API გასაღები", type="password", key="api_key_input")
            submit_register = st.form_submit_button("რეგისტრაცია")
            
            if submit_register:
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

def create_qr_code(url):
    """Create a QR code for the given URL"""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")
        buffered = BytesIO()
        qr_image.save(buffered, format="PNG")
        return buffered.getvalue()
    except Exception as e:
        logger.error(f"QR code creation error: {str(e)}")
        return None

def show_user_header():
    """Display user header with logout button"""
    if st.session_state.get('authenticated', False):
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("🚪 გასვლა", key="logout_button", type="primary"):
                clear_session()
                st.rerun()
        with col1:
            st.markdown(
                f'<div class="user-info"><span>👤 {st.session_state.username}</span></div>',
                unsafe_allow_html=True
            )

# Part 4: Core Functionality and Main Logic

@handle_error
def display_input_page():
    """Display the input form page"""
    st.markdown('<div class="input-container">', unsafe_allow_html=True)

    # Create two rows with four columns each
    row1_col1, row1_col2, row1_col3, row1_col4 = st.columns(4)
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)

    # First row inputs
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

    # Second row inputs
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

    # Generate button section
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("✨ შექმენი სურათი", type="primary", use_container_width=True, key="generate_button"):
            if not name:
                show_error_message("გთხოვთ შეიყვანოთ სახელი", show_retry=False)
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

def translate_user_data(user_data):
    """Translate Georgian user data to English"""
    return {
        "name": user_data['name'],
        "age": user_data['age'],
        "hobby": hobbies[user_data['hobby_category']][user_data['hobby']],
        "color": colors[user_data['color']],
        "style": styles[user_data['style']],
        "mood": moods[user_data['mood']],
        "filter": filters[user_data['filter']]
    }

def create_personalized_prompt(user_data):
    """Create a personalized English prompt based on translated user information"""
    try:
        eng_data = translate_user_data(user_data)

        prompt_request = f"""
        Create a detailed image prompt for a {eng_data['age']}-year-old named {eng_data['name']} 
        who loves {eng_data['hobby']}. 

        Key elements to incorporate:
        - Favorite color: {eng_data['color']}
        - Visual style: {eng_data['style']}
        - Mood: {eng_data['mood']}
        - Filter effect: {eng_data['filter']}

        Create a personalized, artistic scene that captures their interests and personality.
        Focus on cinematic composition, dramatic lighting, and high-quality details.
        Make it engaging and suitable for an expo demonstration.
        Ensure the image is family-friendly and appropriate for all ages.
        """

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an expert at crafting detailed image generation prompts. Focus on creating vivid, specific descriptions that work well with DALL-E 3."},
                {"role": "user", "content": prompt_request}
            ],
            temperature=0.7
        )

        english_prompt = response.choices[0].message.content

        georgian_summary = f"""🎨 რას ვქმნით: 
        პერსონალიზებული სურათი {user_data['name']}-სთვის
        • ჰობი: {user_data['hobby']}
        • სტილი: {user_data['style']}
        • განწყობა: {user_data['mood']}
        • ფილტრი: {user_data['filter']}
        """

        return english_prompt, georgian_summary

    except Exception as e:
        logger.error(f"Error creating prompt: {str(e)}")
        return None, None

def generate_dalle_image(prompt):
    """Generate image using DALL-E 3"""
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            style="vivid",
            n=1
        )
        return response.data[0].url
    except Exception as e:
        logger.error(f"Error generating image: {str(e)}")
        return None

@handle_error
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

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(
                        f'<a href="{image_url}" class="download-button" '
                        f'download="ai_image.png" target="_blank">📥 გადმოწერა</a>',
                        unsafe_allow_html=True
                    )
                with col2:
                    if st.button("🔄 ახალი სურათი", type="primary", key="new_image"):
                        st.session_state.page = 'input'
                        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

@handle_error
def main():
    """Main application function"""
    # Initialize session state
    init_session_state()
    
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

    try:
        if not st.session_state.get('authenticated', False):
            show_auth_page()
        else:
            global client
            client = OpenAI(api_key=st.session_state.api_key)
            
            if st.session_state.get('page', 'input') == 'input':
                display_input_page()
            else:
                display_generation_page()
                
    except Exception as e:
        show_error_message(e)
        if "API" in str(e):
            st.session_state.authenticated = False
            st.rerun()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        show_error_message(e)
