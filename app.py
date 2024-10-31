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

# Database setup
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
    c.execute(
        "SELECT password_hash, api_key FROM users WHERE username = ?",
        (username,)
    )
    result = c.fetchone()
    conn.close()
    
    if result and result[0] == hash_password(password):
        return result[1]  # Return API key
    return None

# Initialize the database
init_db()

# Must be the first Streamlit command
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

# Custom styling
st.markdown("""
    <style>
    /* Hide Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Control width and padding */
    .block-container {
        max-width: 1000px !important;
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }

    /* Base theme */
    .stApp {
        background: linear-gradient(150deg, #1a1a2e 0%, #16213e 100%);
        color: white;
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

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(255, 154, 158, 0.4);
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

    /* Progress bar */
    .stProgress > div > div > div {
        background: linear-gradient(45deg, #FF9A9E, #FAD0C4);
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 0.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        border-radius: 8px;
    }

    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background: rgba(255, 255, 255, 0.1);
    }

    /* Responsive images */
    img {
        max-width: 100%;
        height: auto;
    }

    /* Header styling */
    .header {
        text-align: center;
        margin-bottom: 2rem;
    }

    /* Make columns more compact */
    .stColumn {
        padding: 0 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

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

# Helper Functions
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
        st.error(f"QR კოდის შექმნის შეცდომა: {str(e)}")
        return None

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
                {"role": "system",
                 "content": "You are an expert at crafting detailed image generation prompts. Focus on creating vivid, specific descriptions that work well with DALL-E 3."},
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
        st.error(f"შეცდომა პრომპტის შექმნისას: {str(e)}")
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
        st.error(f"შეცდომა სურათის გენერაციისას: {str(e)}")
        return None

def add_to_history(image_url, prompt):
    """Add generated image to history"""
    if len(st.session_state.history) >= 5:
        st.session_state.history.pop(0)

    st.session_state.history.append({
        'url': image_url,
        'prompt': prompt,
        'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
    })

def show_auth_page():
    """Display authentication page"""
    st.markdown('<div class="auth-container">', unsafe_allow_html=True)
    st.title("მოგესალმებით! 👋")
    
    tab1, tab2 = st.tabs(["შესვლა", "რეგისტრაცია"])
    
    with tab1:
        with st.form("login_form"):
            login_username = st.text_input("მომხმარებელი")
            login_password = st.text_input("პა
