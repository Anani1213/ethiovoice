"""
EthioVoice AI — Voice & Text Telecom Assistant
Competition build for Ethio Telecom.
Run with: streamlit run app.py
"""

import streamlit as st
import random
import re
import difflib
from datetime import datetime

# Optional real browser microphone input (Web Speech API via streamlit-mic-recorder)
try:
    from streamlit_mic_recorder import speech_to_text
    MIC_AVAILABLE = True
except ImportError:
    MIC_AVAILABLE = False

UNLIMITED = "ያልተገደበ (Unlimited)"

# =========================================================
# PAGE CONFIG + ACCESSIBILITY-FIRST CSS
# =========================================================
st.set_page_config(page_title="EthioVoice AI", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="css"]  {
        font-size: 19px !important;
    }
    h1 { font-size: 2.1rem !important; }
    h2, h3 { font-size: 1.4rem !important; }
    .stButton > button {
        font-size: 1.15rem !important;
        font-weight: 600 !important;
        padding: 0.9em 1.2em !important;
        border-radius: 14px !important;
        border: 2px solid #0b6623 !important;
        min-height: 3.2em;
        width: 100%;
    }
    .stTextInput > div > div > input {
        font-size: 1.1rem !important;
        padding: 0.7em !important;
    }
    .badge-success {
        display: inline-block;
        background-color: #d4edda;
        color: #0b6623;
        border: 2px solid #0b6623;
        padding: 10px 18px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 8px;
    }
    .badge-error {
        display: inline-block;
        background-color: #f8d7da;
        color: #842029;
        border: 2px solid #842029;
        padding: 10px 18px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 8px;
    }
    .info-card {
        background-color: #f5f9ff;
        border: 2px solid #cfe0f5;
        border-radius: 14px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .pkg-price {
        font-size: 1.3rem;
        font-weight: 800;
        color: #0b6623;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "balance": 125.50,           # ETB airtime
    "data_balance": 2.3,         # GB (float) or UNLIMITED string
    "voice_minutes": 45,         # int or UNLIMITED string
    "sms_balance": 50,
    "telebirr_balance": 850.00,
    "history": [],
    "recognized_text": "",
    "last_audio_hash": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# =========================================================
# NORMALIZATION (handles typos, slang, spelling variants)
# =========================================================
AMHARIC_NORMALIZATION_MAP = {
    "ሒ": "ሂ", "ሓ": "ሀ", "ኅ": "ህ", "ሑ": "ሁ", "ኁ": "ሁ",
    "ሔ": "ሄ", "ኄ": "ሄ", "ሕ": "ህ", "ሖ": "ሆ", "ኆ": "ሆ",
    "ሠ": "ሰ", "ሡ": "ሱ", "ሢ": "ሲ", "ሣ": "ሳ", "ሤ": "ሴ",
    "ሥ": "ስ", "ሦ": "ሶ", "ዐ": "አ", "ዑ": "ኡ", "ዒ": "ኢ",
    "ዓ": "ኣ", "ዔ": "ኤ", "ዕ": "እ", "ዖ": "ኦ", "ፀ": "ጸ",
    "ፁ": "ጹ", "ፂ": "ጺ", "ፃ": "ጻ", "ፄ": "ጼ", "ፅ": "ጽ",
    "ፆ": "ጾ", "ፓኬጂ": "ፓኬጅ",
}


def normalize_text(text):
    if not text:
        return ""
    text = text.strip().lower()
    for variant, canonical in AMHARIC_NORMALIZATION_MAP.items():
        text = text.replace(variant, canonical)
    text = re.sub(r"[፣፤፥፦፧፨.,!?;:\"'()\[\]*#]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# =========================================================
# INTENT KEYWORDS + FUZZY MATCHING
# =========================================================
INTENT_KEYWORDS = {
    "check_balance": [
        "ቀሪ", "ሂሳብ", "ሒሳብ", "ብር", "ስንት አለኝ", "ያለኝ", "balance", "804"
    ],
    "buy_package": [
        "ፓኬጅ", "ፓኬጂ", "ጥቅል", "ኢንተርኔት", "ዳታ", "ደቂቃ",
        "ሳምንታዊ", "ወርሃዊ", "package", "bundle"
    ],
    "telebirr_transfer": [
        "ላክ", "መላክ", "ትራንስፈር", "ቴሌብር", "ገንዘብ", "send", "transfer"
    ],
}

FUZZY_THRESHOLD = 0.78  # similarity ratio for typo tolerance


def keyword_matches(keyword, normalized_text):
    """Exact substring match first, then per-word fuzzy match for typos/accents."""
    norm_keyword = normalize_text(keyword)
    if norm_keyword in normalized_text:
        return True
    for word in normalized_text.split():
        if difflib.SequenceMatcher(None, word, norm_keyword).ratio() >= FUZZY_THRESHOLD:
            return True
    return False


def detect_intent(raw_text):
    """
    Returns (intent, matched_intents_list).
    intent is one of: check_balance, buy_package, telebirr_transfer,
                       'ambiguous', 'unknown'
    """
    normalized = normalize_text(raw_text)
    if not normalized:
        return "unknown", []

    matched = []
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword_matches(k, normalized) for k in keywords):
            matched.append(intent)

    if len(matched) == 1:
        return matched[0], matched
    elif len(matched) > 1:
        return "ambiguous", matched
    else:
        return "unknown", []


# =========================================================
# ETHIO TELECOM PACKAGE CATALOG
# =========================================================
PACKAGES = {
    "daily": [
        {"id": "d1", "name": "100MB ቀናዊ ጥቅል", "data_mb": 100, "price": 10, "validity": "1 ቀን"},
        {"id": "d2", "name": "300MB ቀናዊ ጥቅል", "data_mb": 300, "price": 18, "validity": "1 ቀን"},
        {"id": "d3", "name": "500MB ቀናዊ ጥቅል", "data_mb": 500, "price": 25, "validity": "1 ቀን"},
    ],
    "weekly": [
        {"id": "w1", "name": "1GB ሳምንታዊ ጥቅል", "data_mb": 1024, "price": 70, "validity": "7 ቀናት"},
        {"id": "w2", "name": "3GB ሳምንታዊ ጥቅል", "data_mb": 3072, "price": 150, "validity": "7 ቀናት"},
        {"id": "w3", "name": "5GB ሳምንታዊ ጥቅል", "data_mb": 5120, "price": 220, "validity": "7 ቀናት"},
    ],
    "monthly": [
        {"id": "m1", "name": "10GB ወርሃዊ ጥቅል", "data_mb": 10240, "price": 350, "validity": "30 ቀናት"},
        {"id": "m2", "name": "20GB ወርሃዊ ጥቅል", "data_mb": 20480, "price": 600, "validity": "30 ቀናት"},
        {"id": "m3", "name": "ያልተገደበ ኢንተርኔት ወርሃዊ ጥቅል", "data_mb": None, "unlimited_data": True,
         "price": 900, "validity": "30 ቀናት"},
    ],
    "combo": [
        {"id": "c1", "name": "ኮምቦ: 200 ደቂቃ + 200 ኤስኤምኤስ + 1GB", "minutes": 200, "sms": 200,
         "data_mb": 1024, "price": 120, "validity": "7 ቀናት"},
        {"id": "c2", "name": "ኮምቦ: 500 ደቂቃ + 500 ኤስኤምኤስ + 5GB", "minutes": 500, "sms": 500,
         "data_mb": 5120, "price": 350, "validity": "30 ቀናት"},
        {"id": "c3", "name": "ኮምቦ: ያልተገደበ ደቂቃ + 10GB ዳታ", "minutes": None, "unlimited_minutes": True,
         "sms": 0, "data_mb": 10240, "price": 500, "validity": "30 ቀናት"},
    ],
}

CATEGORY_LABELS = {
    "daily": "🌞 ቀናዊ ጥቅሎች (Daily)",
    "weekly": "📅 ሳምንታዊ ጥቅሎች (Weekly)",
    "monthly": "🗓️ ወርሃዊ ጥቅሎች (Monthly)",
    "combo": "🎁 ኮምቦ ጥቅሎች (Voice+SMS+Data)",
}


# =========================================================
# HELPERS
# =========================================================
def format_data(value):
    if value == UNLIMITED:
        return UNLIMITED
    if value >= 1024:
        return f"{value/1024:.1f} ጂቢ (GB)"
    return f"{value:.0f} ሜባ (MB)"


def format_minutes(value):
    if value == UNLIMITED:
        return UNLIMITED
    return f"{value} ደቂቃ"


def log_activity(text):
    st.session_state.history.append(f"{datetime.now().strftime('%H:%M')} - {text}")


# =========================================================
# CORE FEATURE FUNCTIONS
# =========================================================
def check_balance_text():
    return (
        f"📞 የአየር ሰዓት ቀሪ ሂሳብ: **{st.session_state.balance:.2f} ብር**\n\n"
        f"📶 ዳታ ቀሪ: **{format_data(st.session_state.data_balance)}**\n\n"
        f"🗣️ ድምጽ ቀሪ: **{format_minutes(st.session_state.voice_minutes)}**\n\n"
        f"✉️ ኤስኤምኤስ ቀሪ: **{st.session_state.sms_balance}**"
    )


def find_package(category, pkg_id):
    for pkg in PACKAGES.get(category, []):
        if pkg["id"] == pkg_id:
            return pkg
    return None


def buy_package(category, pkg_id):
    pkg = find_package(category, pkg_id)
    if not pkg:
        return False, "⚠️ ይቅርታ፣ የተመረጠው ጥቅል አልተገኘም።"

    if st.session_state.balance < pkg["price"]:
        return False, (
            f"⚠️ በቂ ሂሳብ የለዎትም። የ{pkg['name']} ዋጋ {pkg['price']} ብር ሲሆን "
            f"የአሁኑ ቀሪ ሂሳብዎ {st.session_state.balance:.2f} ብር ብቻ ነው። "
            f"እባክዎ አየር ሰዓት ይሙሉ።"
        )

    st.session_state.balance -= pkg["price"]

    # Data
    if pkg.get("unlimited_data"):
        st.session_state.data_balance = UNLIMITED
    elif pkg.get("data_mb") and st.session_state.data_balance != UNLIMITED:
        st.session_state.data_balance += pkg["data_mb"] / 1024

    # Minutes
    if pkg.get("unlimited_minutes"):
        st.session_state.voice_minutes = UNLIMITED
    elif pkg.get("minutes") and st.session_state.voice_minutes != UNLIMITED:
        st.session_state.voice_minutes += pkg["minutes"]

    # SMS
    if pkg.get("sms"):
        st.session_state.sms_balance += pkg["sms"]

    log_activity(f"ግዢ: {pkg['name']} ({pkg['price']} ብር)")
    return True, (
        f"✅ የ{pkg['name']} ጥቅል በተሳካ ሁኔታ ተገዝቷል!\n\n"
        f"💰 ተቀናሽ የተደረገ: {pkg['price']} ብር\n"
        f"💳 አዲስ ቀሪ ሂሳብ: {st.session_state.balance:.2f} ብር\n"
        f"⏳ ልክነት: {pkg['validity']}"
    )


def telebirr_transfer(phone, amount_str):
    phone = (phone or "").strip()
    try:
        amount = float(amount_str)
    except (ValueError, TypeError):
        return False, "⚠️ እባክዎ ትክክለኛ የገንዘብ መጠን ያስገቡ።"

    if len(phone) < 9:
        return False, "⚠️ እባክዎ ትክክለኛ የስልክ ቁጥር ያስገቡ (ለምሳሌ 0912345678)።"
    if amount <= 0:
        return False, "⚠️ የሚላከው መጠን ከዜሮ በላይ መሆን አለበት።"
    if amount > st.session_state.telebirr_balance:
        return False, (
            f"⚠️ በቴሌብር ሂሳብዎ በቂ ገንዘብ የለም። "
            f"የአሁኑ ቀሪ ሂሳብ: {st.session_state.telebirr_balance:.2f} ብር።"
        )

    st.session_state.telebirr_balance -= amount
    txn_id = f"TB{random.randint(100000, 999999)}"
    log_activity(f"ማስተላለፍ: {amount:.2f} ብር ወደ {phone}")
    return True, (
        f"✅ **{amount:.2f} ብር** ወደ **{phone}** በተሳካ ሁኔታ ተልኳል!\n\n"
        f"🧾 የግብይት መለያ: `{txn_id}`\n"
        f"💳 አዲስ የቴሌብር ቀሪ ሂሳብ: {st.session_state.telebirr_balance:.2f} ብር"
    )


# =========================================================
# SIDEBAR — JUDGE / TEST MODE
# =========================================================
with st.sidebar:
    st.header("🧪 Judge / Test Mode")
    st.caption("Set custom balances to test any feature instantly.")

    sim_balance = st.number_input("Airtime Balance (ETB)", min_value=0.0,
                                   value=float(st.session_state.balance), step=10.0, format="%.2f")
    sim_telebirr = st.number_input("Telebirr Balance (ETB)", min_value=0.0,
                                    value=float(st.session_state.telebirr_balance), step=50.0, format="%.2f")
    current_data = 0.0 if st.session_state.data_balance == UNLIMITED else float(st.session_state.data_balance)
    sim_data = st.number_input("Data Balance (GB)", min_value=0.0, value=current_data, step=0.5, format="%.1f")
    current_min = 0 if st.session_state.voice_minutes == UNLIMITED else int(st.session_state.voice_minutes)
    sim_minutes = st.number_input("Voice Minutes", min_value=0, value=current_min, step=10)

    if st.button("✅ Apply Simulated Balance"):
        st.session_state.balance = sim_balance
        st.session_state.telebirr_balance = sim_telebirr
        st.session_state.data_balance = sim_data
        st.session_state.voice_minutes = sim_minutes
        st.success("Balances updated!")
        st.rerun()

    st.markdown("---")
    if not MIC_AVAILABLE:
        st.warning("🎤 Voice input needs: `pip install streamlit-mic-recorder`")

    with st.expander("🔍 Debug: Intent Keywords"):
        for intent, kws in INTENT_KEYWORDS.items():
            st.caption(f"**{intent}**: {', '.join(kws)}")


# =========================================================
# MAIN HEADER
# =========================================================
st.title("🎙️ EthioVoice AI")
st.caption("Voice & Text Telecom Assistant — ለሁሉም ተደራሽ የኢትዮ ቴሌኮም ረዳት")

tab1, tab2, tab3, tab4 = st.tabs([
    "🎙️ የድምፅ/ጽሁፍ ትእዛዝ",
    "📊 ቀሪ ሂሳብ",
    "📦 የፓኬጅ ዝርዝሮች",
    "💸 ቴሌብር ማስተላለፊያ",
])


# =========================================================
# TAB 1 — VOICE & TEXT CONSOLE
# =========================================================
with tab1:
    st.subheader("🎙️ የድምፅ ወይም ጽሁፍ ትእዛዝ ይስጡ")
    st.caption("Speak or type your command in Amharic — slang, typos, and accents are okay.")

    voice_text = None
    if MIC_AVAILABLE:
        voice_text = speech_to_text(
            language="am-ET",
            start_prompt="🎤 መናገር ጀምር (Start Speaking)",
            stop_prompt="⏹️ አቁም (Stop)",
            just_once=True,
            use_container_width=True,
            key="mic_input",
        )
        if voice_text:
            st.markdown(f"<div class='info-card'>🗣️ የተያዘ ንግግር: <b>{voice_text}</b></div>",
                        unsafe_allow_html=True)
    else:
        st.info("🎤 Real voice input unavailable — install `streamlit-mic-recorder` to enable it. Text works below.")

    typed_text = st.text_input("✏️ ወይም እዚህ ይተይቡ (Or type here)", key="typed_command")

    process = st.button("➡️ ትእዛዝ አስፈጽም (Process Command)")

    final_command = voice_text if voice_text else typed_text

    if process:
        if not final_command:
            st.markdown("<span class='badge-error'>እባክዎ በመጀመሪያ ይናገሩ ወይም ይተይቡ።</span>",
                        unsafe_allow_html=True)
        else:
            intent, matched = detect_intent(final_command)

            with st.expander("🔍 Debug: Matching Details"):
                st.text(f"Raw: {final_command}")
                st.text(f"Normalized: {normalize_text(final_command)}")
                st.text(f"Matched intents: {matched}")
                st.text(f"Final intent: {intent}")

            st.markdown("---")
            if intent == "check_balance":
                st.markdown("<span class='badge-success'>✅ ቀሪ ሂሳብ ተገኝቷል</span>", unsafe_allow_html=True)
                st.markdown(check_balance_text())

            elif intent == "buy_package":
                st.info("📦 ጥቅል መግዛት ይፈልጋሉ። እባክዎ ከ«📦 የፓኬጅ ዝርዝሮች» ትር ውስጥ የሚፈልጉትን ጥቅል ይምረጡ።")

            elif intent == "telebirr_transfer":
                st.info("💸 ገንዘብ ማስተላለፍ ይፈልጋሉ። እባክዎ ከ«💸 ቴሌብር ማስተላለፊያ» ትር ውስጥ ዝርዝሮችን ያስገቡ።")

            elif intent == "ambiguous":
                readable = " / ".join(matched)
                st.warning(
                    f"🤔 ትእዛዝዎ ከአንድ በላይ አገልግሎት ጋር ይመሳሰላል ({readable})። "
                    f"እባክዎ በግልጽ ይናገሩ፦ 'ቀሪ ሂሳብ አሳየኝ'፣ 'ጥቅል መግዛት እፈልጋለሁ'፣ ወይም 'ገንዘብ ላክ'።"
                )

            else:
                st.warning(
                    "😕 ይቅርታ፣ በትክክል አልተረዳሁትም። እባክዎ በሚከተለው መልኩ ይሞክሩ፦\n\n"
                    "- «ቀሪ ሂሳቤን አሳየኝ» (ለቀሪ ሂሳብ)\n"
                    "- «ጥቅል መግዛት እፈልጋለሁ» (ለፓኬጅ ግዢ)\n"
                    "- «ገንዘብ ወደ ቴሌብር ላክ» (ለቴሌብር ማስተላለፍ)"
                )


# =========================================================
# TAB 2 — BALANCE CHECK
# =========================================================
with tab2:
    st.subheader("📊 ቀሪ ሂሳብ (*804#)")
    c1, c2 = st.columns(2)
    c1.metric("📞 አየር ሰዓት", f"{st.session_state.balance:.2f} ብር")
    c2.metric("💳 ቴሌብር", f"{st.session_state.telebirr_balance:.2f} ብር")
    c3, c4 = st.columns(2)
    c3.metric("📶 ዳታ", format_data(st.session_state.data_balance))
    c4.metric("🗣️ ደቂቃ", format_minutes(st.session_state.voice_minutes))
    st.metric("✉️ ኤስኤምኤስ", st.session_state.sms_balance)

    if st.button("🔄 ቀሪ ሂሳብ አድስ (Refresh)"):
        st.rerun()


# =========================================================
# TAB 3 — PACKAGE STORE
# =========================================================
with tab3:
    st.subheader("📦 የፓኬጅ ዝርዝሮች")
    category = st.selectbox("ምድብ ይምረጡ (Choose category)",
                             list(CATEGORY_LABELS.keys()),
                             format_func=lambda c: CATEGORY_LABELS[c])

    for pkg in PACKAGES[category]:
        with st.container():
            st.markdown(f"<div class='info-card'>", unsafe_allow_html=True)
            colA, colB = st.columns([3, 1])
            with colA:
                st.markdown(f"**{pkg['name']}**")
                details = []
                if pkg.get("unlimited_data"):
                    details.append(f"ዳታ: {UNLIMITED}")
                elif pkg.get("data_mb"):
                    details.append(f"ዳታ: {format_data(pkg['data_mb'])}")
                if pkg.get("unlimited_minutes"):
                    details.append(f"ደቂቃ: {UNLIMITED}")
                elif pkg.get("minutes"):
                    details.append(f"ደቂቃ: {pkg['minutes']}")
                if pkg.get("sms"):
                    details.append(f"ኤስኤምኤስ: {pkg['sms']}")
                details.append(f"ልክነት: {pkg['validity']}")
                st.caption(" | ".join(details))
                st.markdown(f"<span class='pkg-price'>{pkg['price']} ብር</span>", unsafe_allow_html=True)
            with colB:
                if st.button("ግዛ", key=f"buy_{pkg['id']}"):
                    success, msg = buy_package(category, pkg["id"])
                    if success:
                        st.markdown("<span class='badge-success'>✅ ተሳክቷል!</span>", unsafe_allow_html=True)
                        st.markdown(msg)
                        st.rerun()
                    else:
                        st.markdown("<span class='badge-error'>❌ አልተሳካም</span>", unsafe_allow_html=True)
                        st.markdown(msg)
            st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# TAB 4 — TELEBIRR TRANSFER
# =========================================================
with tab4:
    st.subheader("💸 ቴሌብር ማስተላለፊያ")
    st.metric("💳 የአሁኑ ቴሌብር ቀሪ ሂሳብ", f"{st.session_state.telebirr_balance:.2f} ብር")

    phone_number = st.text_input("📱 የተቀባይ ስልክ ቁጥር", placeholder="0912345678")
    amount = st.text_input("💰 የሚላከው መጠን (ብር)", placeholder="ለምሳሌ 100")

    if st.button("➡️ ገንዘብ ላክ (Send Money)"):
        success, msg = telebirr_transfer(phone_number, amount)
        if success:
            st.markdown("<span class='badge-success'>✅ ግብይት ተሳክቷል!</span>", unsafe_allow_html=True)
            st.markdown(msg)
            st.rerun()
        else:
            st.markdown("<span class='badge-error'>❌ ግብይት አልተሳካም</span>", unsafe_allow_html=True)
            st.markdown(msg)


# =========================================================
# ACTIVITY HISTORY (shown on every tab visit, at bottom)
# =========================================================
st.markdown("---")
st.markdown("### 🕒 የቅርብ ጊዜ እንቅስቃሴ (Recent Activity)")
if st.session_state.history:
    for h in reversed(st.session_state.history[-6:]):
        st.text(h)
else:
    st.text("ምንም እንቅስቃሴ የለም።")

st.caption(
    "⚠️ ማሳሰቢያ: ይህ የማሳያ (Demo) ስሪት ነው። ትክክለኛ ገንዘብ አይንቀሳቀስም። / "
    "This is a simulation for demo purposes only — no real transactions occur."
    )
