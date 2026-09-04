"""
EthioVoice AI - Amharic Voice Assistant Simulator
Simulates Ethio Telecom & Telebirr services via voice/text commands.
Run with: streamlit run app.py
"""

import streamlit as st
import json
import random
from datetime import datetime

# Optional real microphone input (browser Web Speech API via streamlit-mic-recorder)
try:
    from streamlit_mic_recorder import speech_to_text
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

# ---------- Load Configuration ----------
with open("prompts.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

st.set_page_config(page_title="EthioVoice AI", page_icon="🎙️", layout="centered")

# ---------- Simulated User Account State ----------
if "balance" not in st.session_state:
    st.session_state.balance = 125.50       # ETB airtime balance
if "data_balance" not in st.session_state:
    st.session_state.data_balance = 2.3     # GB
if "voice_minutes" not in st.session_state:
    st.session_state.voice_minutes = 45
if "telebirr_balance" not in st.session_state:
    st.session_state.telebirr_balance = 850.00
if "history" not in st.session_state:
    st.session_state.history = []


# ---------- Intent Detection (Keyword-based NLU) ----------
def detect_intent(text):
    text = text.strip().lower()
    for intent_name, intent_data in CONFIG["intents"].items():
        for keyword in intent_data["keywords"]:
            if keyword.lower() in text:
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


# ---------- Sidebar: Judge / Demo Mode ----------
with st.sidebar:
    st.header("🧪 Judge / Test Mode")
    st.caption("Set custom account values here to test the balance check, "
               "package purchase, and Telebirr features on demand.")

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
    if not MIC_AVAILABLE:
        st.warning(
            "🎤 Microphone input package not installed.\n\n"
            "Run: `pip install streamlit-mic-recorder`"
        )


# ---------- Main UI ----------
st.title("🎙️ EthioVoice AI")
st.caption(CONFIG["system"]["tagline"])

st.markdown("### 🗣️ የድምጽ ትዕዛዝዎን ይናገሩ ወይም ይተይቡ (Speak or type your command)")

voice_text = None
if MIC_AVAILABLE:
    st.caption("🎤 Tap once to start, tap again to stop. Requires microphone "
               "permission and works best in Chrome. Needs HTTPS or localhost.")
    voice_text = speech_to_text(
        language="am-ET",
        start_prompt="🎤 መናገር ጀምር (Start Speaking)",
        stop_prompt="⏹️ አቁም (Stop)",
        just_once=True,
        use_container_width=True,
        key="mic_input",
    )
    if voice_text:
        st.info(f"🗣️ የተያዘ ንግግር (Recognized speech): **{voice_text}**")

typed_input = st.text_input(
    "ወይም እዚህ ይተይቡ (Or type here) — ለምሳሌ፦ «ቀሪ ሂሳቤን አሳየኝ»",
    key="typed_input",
)

col1, col2 = st.columns(2)
with col1:
    process_btn = st.button("➡️ ላክ (Process)")
with col2:
    clear_btn = st.button("🧹 አጽዳ (Clear)")

if clear_btn:
    st.session_state.pop("typed_input", None)
    st.rerun()

final_command = voice_text if voice_text else typed_input

if process_btn and final_command:
    intent = detect_intent(final_command)
    st.markdown("---")
    if intent == "check_balance":
        st.success(check_balance())
    elif intent == "buy_package":
        st.info(CONFIG["responses"]["ask_package_choice"])
    elif intent == "telebirr_transfer":
        st.info(CONFIG["responses"]["ask_transfer_details"])
    else:
        st.warning(CONFIG["responses"]["unknown_intent"])
elif process_btn and not final_command:
    st.warning("እባክዎ በመጀመሪያ ትዕዛዝ ይናገሩ ወይም ይተይቡ። (Please speak or type a command first.)")

st.markdown("---")

# ---------- Manual Feature Panels (for demo reliability) ----------
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
