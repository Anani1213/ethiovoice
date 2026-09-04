"""
EthioVoice AI - Amharic Voice Assistant Simulator
Simulates Ethio Telecom & Telebirr services via real browser voice recording.
Run with: streamlit run app.py
"""

import streamlit as st
import json
import random
import io
import re
import hashlib
from datetime import datetime

try:
    from openai import OpenAI
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False

# ---------- Load Configuration ----------
with open("prompts.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

st.set_page_config(page_title="EthioVoice AI", page_icon="🎙️", layout="centered")

# ---------- Simulated User Account State ----------
if "balance" not in st.session_state:
    st.session_state.balance = 125.50
if "data_balance" not in st.session_state:
    st.session_state.data_balance = 2.3
if "voice_minutes" not in st.session_state:
    st.session_state.voice_minutes = 45
if "telebirr_balance" not in st.session_state:
    st.session_state.telebirr_balance = 850.00
if "history" not in st.session_state:
    st.session_state.history = []
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None
if "recognized_text" not in st.session_state:
    st.session_state.recognized_text = ""

# Sample phrases used for simulated recognition mode
DEMO_PHRASES = {
    "check_balance": "ቀሪ ሂሳቤን አሳየኝ",
    "buy_package": "ጥቅል መግዛት እፈልጋለሁ",
    "telebirr_transfer": "ገንዘብ ወደ ቴሌብር ላክ",
}

# ---------- Intent Keyword Definitions ----------
INTENT_KEYWORDS = {
    "check_balance": ["ቀሪ", "ሂሳብ", "ሒሳብ", "ብር", "ያለኝ", "balance", "804"],
    "buy_package": ["ፓኬጅ", "ፓኬጂ", "ጥቅል", "ኢንተርኔት", "ደቂቃ", "package", "bundle"],
    "telebirr_transfer": ["ላክ", "መላክ", "ትራንስፈር", "ቴሌብር", "transfer", "send"],
}

# Amharic character-variation normalization map
# (maps visually/phonetically similar variants to one canonical form)
AMHARIC_NORMALIZATION_MAP = {
    "ሒ": "ሂ",
    "ሓ": "ሀ",
    "ኅ": "ሀ",
    "ሑ": "ሁ",
    "ኁ": "ሁ",
    "ሔ": "ሄ",
    "ኄ": "ሄ",
    "ሕ": "ህ",
    "ኅ": "ህ",
    "ሖ": "ሆ",
    "ኆ": "ሆ",
    "ሠ": "ሰ",
    "ሡ": "ሱ",
    "ሢ": "ሲ",
    "ሣ": "ሳ",
    "ሤ": "ሴ",
    "ሥ": "ስ",
    "ሦ": "ሶ",
    "ዐ": "አ",
    "ዑ": "ኡ",
    "ዒ": "ኢ",
    "ዓ": "ኣ",
    "ዔ": "ኤ",
    "ዕ": "እ",
    "ዖ": "ኦ",
    "ፀ": "ጸ",
    "ፁ": "ጹ",
    "ፂ": "ጺ",
    "ፃ": "ጻ",
    "ፄ": "ጼ",
    "ፅ": "ጽ",
    "ፆ": "ጾ",
}


def normalize_text(text):
    """
    Normalize Amharic (and mixed Amharic/English) text before intent matching:
    - Lowercase (affects any Latin-script words like 'balance', 'send')
    - Replace visually/phonetically similar Amharic character variants
    - Collapse multiple spaces, strip leading/trailing whitespace
    - Remove common punctuation that can break substring matches
    """
    if not text:
        return ""

    text = text.strip().lower()

    # Normalize Amharic character variants
    for variant, canonical in AMHARIC_NORMALIZATION_MAP.items():
        text = text.replace(variant, canonical)

    # Remove punctuation (Amharic + Latin) that could interfere with matching
    text = re.sub(r"[፣፤፥፦፧፨.,!?;:\"'()\[\]]", " ", text)

    # Collapse whitespace (multiple spaces, tabs, newlines -> single space)
    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------- Intent Detection (Keyword / Substring Matching) ----------
def detect_intent(text):
    """
    Detects intent using substring/keyword matching against normalized text.
    Returns the first matching intent, or 'unknown' if no keyword is found.
    """
    normalized = normalize_text(text)

    for intent_name, keywords in INTENT_KEYWORDS.items():
        for keyword in keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword in normalized:
                return intent_name

    return "unknown"


# ---------- Feature Functions ----------
def check_balance():
    return CONFIG["responses"]["check_balance"].format(
        balance=f"{st.session_state.balance:.2f}",
        data=f"{st.session_state.data_balance:.1f}",
        minutes=st.session_state.voice_minutes,
    )


def buy_package(package_key):
    packages = CONFIG["packages"]
    if package_key not in packages:
        return CONFIG["responses"]["package_not_found"]

    pkg = packages[package_key]
    if st.session_state.balance < pkg["price"]:
        return CONFIG["responses"]["insufficient_balance"].format(
            balance=f"{st.session_state.balance:.2f}"
        )

    st.session_state.balance -= pkg["price"]
    if pkg["type"] == "data":
        st.session_state.data_balance += pkg["amount"]
    elif pkg["type"] == "voice":
        st.session_state.voice_minutes += pkg["amount"]

    st.session_state.history.append(
        f"{datetime.now().strftime('%H:%M')} - ግዢ: {pkg['name']}"
    )
    return CONFIG["responses"]["package_success"].format(
        name=pkg["name"], price=pkg["price"], balance=f"{st.session_state.balance:.2f}"
    )


def telebirr_transfer(phone, amount):
    try:
        amount = float(amount)
    except ValueError:
        return CONFIG["responses"]["invalid_amount"]

    if not phone or len(phone.strip()) < 9:
        return CONFIG["responses"]["invalid_phone"]
    if amount <= 0:
        return CONFIG["responses"]["invalid_amount"]
    if amount > st.session_state.telebirr_balance:
        return CONFIG["responses"]["telebirr_insufficient"].format(
            balance=f"{st.session_state.telebirr_balance:.2f}"
        )

    st.session_state.telebirr_balance -= amount
    txn_id = f"TB{random.randint(100000, 999999)}"
    st.session_state.history.append(
        f"{datetime.now().strftime('%H:%M')} - ማስተላለፍ: {amount:.2f} ብር ወደ {phone}"
    )
    return CONFIG["responses"]["telebirr_success"].format(
        amount=f"{amount:.2f}", phone=phone, txn_id=txn_id,
        balance=f"{st.session_state.telebirr_balance:.2f}",
    )


def transcribe_with_whisper(audio_bytes, api_key):
    """Real Amharic transcription via OpenAI Whisper. Raises on failure."""
    client = OpenAI(api_key=api_key)
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "recording.wav"
    result = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        language="am",
    )
    return result.text


# ---------- Sidebar: Judge / Demo Mode ----------
with st.sidebar:
    st.header("🧪 Judge / Test Mode")
    st.caption("Set custom account values to test balance checks, purchases, "
               "and Telebirr transfers on demand.")

    sim_balance = st.number_input(
        "Simulated Airtime Balance (ETB)", min_value=0.0,
        value=float(st.session_state.balance), step=10.0, format="%.2f"
    )
    sim_data = st.number_input(
        "Simulated Data Balance (GB)", min_value=0.0,
        value=float(st.session_state.data_balance), step=0.5, format="%.1f"
    )
    sim_minutes = st.number_input(
        "Simulated Voice Minutes", min_value=0,
        value=int(st.session_state.voice_minutes), step=10
    )
    sim_telebirr = st.number_input(
        "Simulated Telebirr Balance (ETB)", min_value=0.0,
        value=float(st.session_state.telebirr_balance), step=50.0, format="%.2f"
    )

    if st.button("✅ Apply Simulated Balance"):
        st.session_state.balance = sim_balance
        st.session_state.data_balance = sim_data
        st.session_state.voice_minutes = sim_minutes
        st.session_state.telebirr_balance = sim_telebirr
        st.success("Simulated balances updated!")
        st.rerun()

    st.markdown("---")
    st.header("🎤 Voice Recognition Mode")
    recognition_mode = st.radio(
        "How should recorded audio be understood?",
        ["🎭 Simulated recognition (no key needed)", "🌐 Real transcription (OpenAI Whisper)"],
        index=0,
    )
    openai_api_key = ""
    if recognition_mode.startswith("🌐"):
        if not OPENAI_SDK_AVAILABLE:
            st.error("`openai` package not installed. Run: `pip install openai`")
        openai_api_key = st.text_input("OpenAI API Key", type="password")
        st.caption("Your key is only used in this session and never stored.")

    st.markdown("---")
    with st.expander("🔍 Debug: Intent Keywords"):
        for intent, kws in INTENT_KEYWORDS.items():
            st.caption(f"**{intent}**: {', '.join(kws)}")


# ---------- Main UI ----------
st.title("🎙️ EthioVoice AI")
st.caption(CONFIG["system"]["tagline"])

st.markdown("### 🗣️ የድምጽ ትዕዛዝዎን ይናገሩ (Speak your command)")

audio_value = st.audio_input("የድምፅ ትእዛዝዎን ይስጡ (Record Voice)")

final_command = None

if audio_value is not None:
    audio_bytes = audio_value.getvalue()
    audio_hash = hashlib.md5(audio_bytes).hexdigest()
    is_new_recording = audio_hash != st.session_state.last_audio_hash

    if is_new_recording:
        st.session_state.last_audio_hash = audio_hash
        st.session_state.recognized_text = ""

    st.markdown("**🔊 የተቀዳ ድምጽ (Your recording):**")
    st.audio(audio_bytes)

    if recognition_mode.startswith("🌐"):
        # ---- Real transcription path ----
        if st.button("➡️ ትዕዛዝ ተርጉም (Transcribe & Process)"):
            if not OPENAI_SDK_AVAILABLE:
                st.error("`openai` package not installed.")
            elif not openai_api_key:
                st.warning("እባክዎ በጎን በኩል OpenAI API Key ያስገቡ። (Please enter an API key in the sidebar.)")
            else:
                with st.spinner("🎧 ድምጽ በመተርጎም ላይ... (Transcribing Amharic speech...)"):
                    try:
                        text = transcribe_with_whisper(audio_bytes, openai_api_key)
                        st.session_state.recognized_text = text
                    except Exception as e:
                        st.error(f"⚠️ ትርጉም አልተሳካም (Transcription failed): {e}")
                        st.session_state.recognized_text = ""
    else:
        # ---- Simulated recognition path ----
        st.info(
            "🎭 **የማሳያ ሁነታ (Demo Mode):** ትክክለኛ ትርጉም ገና አልተገናኘም። "
            "ከታች የተቀዳው ድምጽ ምን እንደሚወክል ይምረጡ።\n\n"
            "*(Real transcription isn't connected in this mode. Select below what "
            "your recording represents, so the assistant can respond as if it heard you.)*"
        )
        demo_choice = st.selectbox(
            "ይህ ድምጽ ምን ማለት ነው? (What does this recording say?)",
            options=list(DEMO_PHRASES.keys()),
            format_func=lambda k: DEMO_PHRASES[k],
            key=f"demo_choice_{audio_hash}",
        )
        if st.button("➡️ ትዕዛዝ አስኪድ (Process as this command)"):
            st.session_state.recognized_text = DEMO_PHRASES[demo_choice]

    if st.session_state.recognized_text:
        st.success(f"🗣️ የተያዘ ንግግር (Recognized speech): **{st.session_state.recognized_text}**")
        final_command = st.session_state.recognized_text

# ---------- Process Recognized Command ----------
if final_command:
    intent = detect_intent(final_command)

    with st.expander("🔍 Debug: Matching Details"):
        st.text(f"Raw text: {final_command}")
        st.text(f"Normalized text: {normalize_text(final_command)}")
        st.text(f"Detected intent: {intent}")

    st.markdown("---")
    if intent == "check_balance":
        st.success(check_balance())
    elif intent == "buy_package":
        st.info(CONFIG["responses"]["ask_package_choice"])
    elif intent == "telebirr_transfer":
        st.info(CONFIG["responses"]["ask_transfer_details"])
    else:
        st.warning(CONFIG["responses"]["unknown_intent"])

st.markdown("---")

# ---------- Manual Feature Panels (guided fallback flow) ----------
tab1, tab2, tab3 = st.tabs(["📊 ቀሪ ሂሳብ", "📦 ጥቅል ግዢ", "💸 ቴሌብር ማስተላለፍ"])

with tab1:
    st.subheader("Check Balance (*804#)")
    if st.button("ቀሪ ሂሳብ አሳይ (Show Balance)"):
        st.success(check_balance())

with tab2:
    st.subheader("Buy Internet / Voice Package")
    package_options = {v["name"]: k for k, v in CONFIG["packages"].items()}
    chosen = st.selectbox("ጥቅል ይምረጡ (Choose a package)", list(package_options.keys()))
    if st.button("ግዛ (Buy)"):
        st.success(buy_package(package_options[chosen]))

with tab3:
    st.subheader("Telebirr Money Transfer (Simulation)")
    phone_number = st.text_input("የተቀባይ ስልክ ቁጥር (Recipient phone)", "09")
    amount = st.text_input("የሚላከው መጠን (Amount in ETB)", "")
    if st.button("ላክ ገንዘብ (Send Money)"):
        st.success(telebirr_transfer(phone_number, amount))

st.markdown("---")
st.markdown("### 🕒 የቅርብ ጊዜ እንቅስቃሴ (Recent Activity)")
if st.session_state.history:
    for h in reversed(st.session_state.history[-5:]):
        st.text(h)
else:
    st.text("ምንም እንቅስቃሴ የለም።")

st.caption(
    "⚠️ ማሳሰቢያ: ይህ የማሳያ (Demo) ስሪት ነው። ትክክለኛ ገንዘብ አይንቀሳቀስም። / "
    "This is a simulation for demo purposes only — no real transactions occur."
            )
