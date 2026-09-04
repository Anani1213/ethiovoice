"""
EthioVoice AI — Voice & Text Telecom Assistant
Now powered by Gemini multimodal audio processing (with automatic model-selection fallback),
plus local fuzzy-matching fallback if no Gemini model is reachable.
Run with: streamlit run app.py
"""

import streamlit as st
import random
import re
import os
import json
import difflib
from datetime import datetime

# Gemini SDK
try:
    import google.generativeai as genai
    from google.generativeai.types import Part
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False

UNLIMITED = "ያልተገደበ (Unlimited)"

# =========================================================
# PAGE CONFIG + ACCESSIBILITY-FIRST CSS
# =========================================================
st.set_page_config(page_title="EthioVoice AI", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="css"]  { font-size: 19px !important; }
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
        display: inline-block; background-color: #d4edda; color: #0b6623;
        border: 2px solid #0b6623; padding: 10px 18px; border-radius: 12px;
        font-weight: 700; font-size: 1.1rem; margin-bottom: 8px;
    }
    .badge-error {
        display: inline-block; background-color: #f8d7da; color: #842029;
        border: 2px solid #842029; padding: 10px 18px; border-radius: 12px;
        font-weight: 700; font-size: 1.1rem; margin-bottom: 8px;
    }
    .badge-ai {
        display: inline-block; background-color: #e7f0ff; color: #1a4d99;
        border: 2px solid #1a4d99; padding: 6px 14px; border-radius: 10px;
        font-weight: 600; font-size: 0.95rem; margin-bottom: 8px;
    }
    .info-card {
        background-color: #f5f9ff; border: 2px solid #cfe0f5;
        border-radius: 14px; padding: 16px; margin-bottom: 10px;
    }
    .pkg-price { font-size: 1.3rem; font-weight: 800; color: #0b6623; }
</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================
defaults = {
    "balance": 125.50,
    "data_balance": 2.3,
    "voice_minutes": 45,
    "sms_balance": 50,
    "telebirr_balance": 850.00,
    "history": [],
    "recognized_text": "",
    "last_audio_hash": None,
    "prefill_phone": "",
    "prefill_amount": "",
    # Caches whichever Gemini model most recently answered successfully.
    "gemini_working_model": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val


# =========================================================
# GEMINI SETUP
# =========================================================
def get_gemini_api_key():
    """Safely fetch the key from Streamlit secrets first, then environment."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


# Modern valid model identifiers – try flash first, then pro.
GEMINI_MODEL_CANDIDATES = ["gemini-1.5-flash", "gemini-1.5-pro"]

GEMINI_API_KEY = get_gemini_api_key()
GEMINI_READY = bool(GEMINI_API_KEY) and GEMINI_SDK_AVAILABLE

if GEMINI_READY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        GEMINI_READY = False

# ------------------------------------------------------------------
# Gemini NLU prompt for text input (includes GREETING intent now)
# ------------------------------------------------------------------
GEMINI_TEXT_PROMPT = """You are the NLU engine for "EthioVoice AI", a voice assistant for Ethio Telecom and Telebirr users who speak Amharic (including slang, typos, and non-standard spelling).

Classify the user's message into EXACTLY one of these intents:
- "GREETING": user says hello, hi, selam, or any friendly greeting
- "CHECK_BALANCE": user wants to check airtime, data, minutes, or SMS balance (like dialing *804#)
- "BUY_PACKAGE": user wants to buy an internet/data or voice/combo package
- "TRANSFER_TELEBIRR": user wants to send money via Telebirr
- "UNKNOWN": the message is ambiguous, unrelated, or unclear

Also extract any relevant parameters mentioned, such as:
- "package_type": e.g. "ዳታ", "ደቂቃ", "ኮምቦ", "ሳምንታዊ", "ወርሃዊ", "ቀናዊ" (only if clearly mentioned)
- "amount": a numeric ETB amount, if mentioned (for transfers or purchases)
- "phone_number": a phone number, if mentioned (for transfers)

Respond ONLY with valid JSON in this exact shape, with no extra text, no markdown fences:
{
  "intent": "GREETING | CHECK_BALANCE | BUY_PACKAGE | TRANSFER_TELEBIRR | UNKNOWN",
  "parameters": {
    "package_type": "string or null",
    "amount": "number or null",
    "phone_number": "string or null"
  },
  "response_amharic": "A short, polite, natural Amharic sentence confirming what you understood, or asking a polite clarifying question if the intent is UNKNOWN. For GREETING, respond with: 'ሰላም! እንኳን ወደ EthioVoice AI በደህና መጡ። የኢትዮ ቴሌኮም እና የቴሌብር አገልግሎቶችን ለመጠቀም 'ቀሪ ሂሳብ'፣ 'ፓኬጅ መግዛት' ወይም 'ገንዘብ መላክ' ብለው ይናገሩ ወይም ይፃፉ።'"
}

Always respond in valid JSON only. Never include commentary outside the JSON object.
"""

# ------------------------------------------------------------------
# Gemini multimodal prompt for audio input
# ------------------------------------------------------------------
GEMINI_AUDIO_PROMPT = """Listen to this Amharic audio recording carefully.
First, transcribe exactly what the user said in Amharic text.
Second, classify the intent into 'GREETING', 'CHECK_BALANCE', 'BUY_PACKAGE', 'TRANSFER_TELEBIRR', or 'UNKNOWN'.
Respond in structured JSON containing:
{
  "transcription": "exact Amharic transcription",
  "intent": "GREETING | CHECK_BALANCE | BUY_PACKAGE | TRANSFER_TELEBIRR | UNKNOWN",
  "amharic_response": "A short, polite, natural Amharic sentence confirming what you understood, or asking a clarifying question. For GREETING, use: 'ሰላም! እንኳን ወደ EthioVoice AI በደህና መጡ። የኢትዮ ቴሌኮም እና የቴሌብር አገልግሎቶችን ለመጠቀም 'ቀሪ ሂሳብ'፣ 'ፓኬጅ መግዛት' ወይም 'ገንዘብ መላክ' ብለው ይናገሩ ወይም ይፃፉ።'"
}
Return only JSON, no markdown fences.
"""


def _build_model_order():
    """Candidate list with last successful model moved to front."""
    working = st.session_state.get("gemini_working_model")
    if working and working in GEMINI_MODEL_CANDIDATES:
        return [working] + [m for m in GEMINI_MODEL_CANDIDATES if m != working]
    return list(GEMINI_MODEL_CANDIDATES)


def _call_gemini_text_model(model_name, user_text):
    """Text‑only NLU call. Raises on failure."""
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=GEMINI_TEXT_PROMPT,
    )
    result = model.generate_content(
        user_text,
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )
    raw_text = result.text.strip()
    raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    parsed = json.loads(raw_text)
    intent = str(parsed.get("intent", "UNKNOWN")).upper()
    if intent not in ("GREETING", "CHECK_BALANCE", "BUY_PACKAGE", "TRANSFER_TELEBIRR", "UNKNOWN"):
        intent = "UNKNOWN"
    params = parsed.get("parameters") or {}
    response_amharic = parsed.get("response_amharic") or ""
    return {
        "intent": intent,
        "parameters": {
            "package_type": params.get("package_type"),
            "amount": params.get("amount"),
            "phone_number": params.get("phone_number"),
        },
        "response_amharic": response_amharic,
        "source": "gemini",
        "model_used": model_name,
    }


def _call_gemini_audio_model(model_name, audio_bytes, mime_type="audio/wav"):
    """Multimodal audio call. Returns dict with transcription, intent, response."""
    model = genai.GenerativeModel(model_name=model_name)
    audio_part = Part(mime_type=mime_type, data=audio_bytes)
    result = model.generate_content(
        [GEMINI_AUDIO_PROMPT, audio_part],
        generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
        },
    )
    raw_text = result.text.strip()
    raw_text = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()
    parsed = json.loads(raw_text)
    transcription = parsed.get("transcription", "")
    intent = str(parsed.get("intent", "UNKNOWN")).upper()
    if intent not in ("GREETING", "CHECK_BALANCE", "BUY_PACKAGE", "TRANSFER_TELEBIRR", "UNKNOWN"):
        intent = "UNKNOWN"
    amharic_response = parsed.get("amharic_response", "")
    return {
        "transcription": transcription,
        "intent": intent,
        "response_amharic": amharic_response,
        "source": "gemini_audio",
        "model_used": model_name,
    }


def classify_intent_with_gemini_text(user_text):
    """Try each text model in order, fallback locally on total failure."""
    last_error = None
    for model_name in _build_model_order():
        try:
            output = _call_gemini_text_model(model_name, user_text)
            st.session_state.gemini_working_model = model_name
            return output
        except Exception as e:
            last_error = e
            if st.session_state.get("gemini_working_model") == model_name:
                st.session_state.gemini_working_model = None
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No Gemini model candidates available.")


def classify_audio_with_gemini(audio_bytes, mime_type="audio/wav"):
    """Try each audio model in order, fallback locally if all fail."""
    last_error = None
    for model_name in _build_model_order():
        try:
            output = _call_gemini_audio_model(model_name, audio_bytes, mime_type)
            st.session_state.gemini_working_model = model_name
            return output
        except Exception as e:
            last_error = e
            if st.session_state.get("gemini_working_model") == model_name:
                st.session_state.gemini_working_model = None
            continue
    if last_error:
        raise last_error
    raise RuntimeError("No Gemini model candidates available.")


# =========================================================
# LOCAL FALLBACK NLU (fuzzy keyword matching)
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

# GREETING added
INTENT_KEYWORDS = {
    "GREETING": ["ሰላም", "ሰላምታ", "ጤና ይስጥልኝ", "ሃይ", "hi", "hello", "hey", "ሄሎ"],
    "CHECK_BALANCE": ["ቀሪ", "ሂሳብ", "ሒሳብ", "ብር", "ስንት አለኝ", "ያለኝ", "balance", "804"],
    "BUY_PACKAGE": ["ፓኬጅ", "ፓኬጂ", "ጥቅል", "ኢንተርኔት", "ዳታ", "ደቂቃ",
                    "ሳምንታዊ", "ወርሃዊ", "package", "bundle"],
    "TRANSFER_TELEBIRR": ["ላክ", "መላክ", "ትራንስፈር", "ቴሌብር", "ገንዘብ", "send", "transfer"],
}

GREETING_RESPONSE = (
    "ሰላም! እንኳን ወደ EthioVoice AI በደህና መጡ። "
    "የኢትዮ ቴሌኮም እና የቴሌብር አገልግሎቶችን ለመጠቀም "
    "'ቀሪ ሂሳብ'፣ 'ፓኬጅ መግዛት' ወይም 'ገንዘብ መላክ' "
    "ብለው ይናገሩ ወይም ይፃፉ።"
)

FALLBACK_RESPONSES = {
    "GREETING": GREETING_RESPONSE,
    "CHECK_BALANCE": "ቀሪ ሂሳብዎን እያሳየሁ ነው።",
    "BUY_PACKAGE": "ጥቅል ለመግዛት እየረዳሁዎት ነው። እባክዎ ከፓኬጅ ዝርዝር ትር ውስጥ ይምረጡ።",
    "TRANSFER_TELEBIRR": "ገንዘብ ለማስተላለፍ እየረዳሁዎት ነው። እባክዎ ዝርዝሮችን ያስገቡ።",
    "AMBIGUOUS": "ትእዛዝዎ ከአንድ በላይ አገልግሎት ጋር ይመሳሰላል። እባክዎ በግልጽ ይንገሩኝ።",
    "UNKNOWN": "ይቅርታ፣ በትክክል አልተረዳሁትም። 'ቀሪ ሂሳብ አሳየኝ'፣ 'ጥቅል መግዛት እፈልጋለሁ'፣ ወይም 'ገንዘብ ላክ' ብለው ይሞክሩ።",
    "EMPTY": "እባክዎ በመጀመሪያ ይናገሩ ወይም ይተይቡ።",
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


def keyword_matches(keyword, normalized_text, threshold=0.78):
    norm_keyword = normalize_text(keyword)
    if norm_keyword in normalized_text:
        return True
    for word in normalized_text.split():
        if difflib.SequenceMatcher(None, word, norm_keyword).ratio() >= threshold:
            return True
    return False


def classify_intent_locally(raw_text):
    """Local fallback NLU for text. Same output structure as Gemini text path."""
    normalized = normalize_text(raw_text)
    if not normalized:
        return {
            "intent": "UNKNOWN", "parameters": {}, "response_amharic": FALLBACK_RESPONSES["EMPTY"],
            "source": "fallback",
        }

    matched = [
        intent for intent, kws in INTENT_KEYWORDS.items()
        if any(keyword_matches(k, normalized) for k in kws)
    ]

    if len(matched) == 1:
        intent = matched[0]
        response = FALLBACK_RESPONSES[intent]
    elif len(matched) > 1:
        # If GREETING is among multiple, treat as greeting (more user friendly)
        if "GREETING" in matched:
            intent = "GREETING"
            response = FALLBACK_RESPONSES["GREETING"]
        else:
            intent = "UNKNOWN"
            response = FALLBACK_RESPONSES["AMBIGUOUS"]
    else:
        intent = "UNKNOWN"
        response = FALLBACK_RESPONSES["UNKNOWN"]

    phone_match = re.search(r"09\d{8}|9\d{8}", normalized)
    amount_match = re.search(r"\b(\d{2,6})\b", normalized)

    return {
        "intent": intent,
        "parameters": {
            "package_type": None,
            "amount": float(amount_match.group(1)) if amount_match else None,
            "phone_number": phone_match.group(0) if phone_match else None,
        },
        "response_amharic": response,
        "source": "fallback",
    }


def understand_command(raw_text):
    """
    Main NLU entry point for text input.
    Tries Gemini first (looping through candidates), falls back to local fuzzy matching.
    """
    if not raw_text or not raw_text.strip():
        return {
            "intent": "UNKNOWN", "parameters": {}, "response_amharic": FALLBACK_RESPONSES["EMPTY"],
            "source": "none",
        }

    if GEMINI_READY:
        try:
            return classify_intent_with_gemini_text(raw_text)
        except Exception as e:
            result = classify_intent_locally(raw_text)
            result["error"] = str(e)
            return result
    else:
        return classify_intent_locally(raw_text)


def process_audio_command(audio_bytes, mime_type="audio/wav"):
    """
    Main NLU entry point for audio input.
    Tries Gemini multimodal; falls back to local text analysis of empty transcription.
    """
    if GEMINI_READY:
        try:
            return classify_audio_with_gemini(audio_bytes, mime_type)
        except Exception as e:
            # Fallback: treat as empty text (will get EMPTY response)
            result = classify_intent_locally("")
            result["error"] = str(e)
            result["source"] = "fallback_audio_error"
            result["transcription"] = ""
            return result
    else:
        return {
            "transcription": "",
            "intent": "UNKNOWN",
            "response_amharic": "ድምጽ ማቀናበር አልተቻለም። እባክዎ በጽሁፍ ይሞክሩ።",
            "source": "no_gemini",
        }


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
            f"የአሁኑ ቀሪ ሂሳብዎ {st.session_state.balance:.2f} ብር ብቻ ነው። እባክዎ አየር ሰዓት ይሙሉ።"
        )

    st.session_state.balance -= pkg["price"]

    if pkg.get("unlimited_data"):
        st.session_state.data_balance = UNLIMITED
    elif pkg.get("data_mb") and st.session_state.data_balance != UNLIMITED:
        st.session_state.data_balance += pkg["data_mb"] / 1024

    if pkg.get("unlimited_minutes"):
        st.session_state.voice_minutes = UNLIMITED
    elif pkg.get("minutes") and st.session_state.voice_minutes != UNLIMITED:
        st.session_state.voice_minutes += pkg["minutes"]

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
            f"⚠️ በቴሌብር ሂሳብዎ በቂ ገንዘብ የለም። የአሁኑ ቀሪ ሂሳብ: {st.session_state.telebirr_balance:.2f} ብር።"
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
    st.header("🧠 NLU Engine Status")
    if GEMINI_READY:
        st.success("✅ Gemini connected")
        st.caption("Model fallback order: " + " → ".join(GEMINI_MODEL_CANDIDATES))
        if st.session_state.gemini_working_model:
            st.caption(f"Last successful model: **{st.session_state.gemini_working_model}**")
    elif not GEMINI_SDK_AVAILABLE:
        st.error("`google-generativeai` not installed.\nRun: `pip install google-generativeai`")
    else:
        st.warning(
            "⚠️ No GEMINI_API_KEY found. Using local fuzzy-matching fallback.\n\n"
            "Add it via `st.secrets['GEMINI_API_KEY']` or the `GEMINI_API_KEY` "
            "environment variable to enable Gemini."
        )

    # No need for mic-recorder warning since we use st.audio_input now
    with st.expander("🔍 Debug: Fallback Keywords"):
        for intent, kws in INTENT_KEYWORDS.items():
            st.caption(f"**{intent}**: {', '.join(kws)}")


# =========================================================
# MAIN HEADER
# =========================================================
st.title("🎙️ EthioVoice AI")
st.caption("Voice & Text Telecom Assistant — powered by Gemini Multimodal NLU")

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
    st.caption("Record your voice or type your command in Amharic — slang, typos, and accents are okay.")

    # --- Audio input (native Streamlit) ---
    audio_input = st.audio_input("ድምፅዎን ይቅረፁ (Record Audio)", key="audio_input")
    transcribed_audio_text = None
    result_from_audio = None

    if audio_input is not None:
        # Read the raw audio bytes
        audio_bytes = audio_input.read()
        if audio_bytes:
            with st.spinner("🎧 ድምፅዎን በመተንተን ላይ... (Analyzing your audio...)"):
                # Assume wav; adjust if necessary based on actual format
                audio_result = process_audio_command(audio_bytes, mime_type="audio/wav")
                result_from_audio = audio_result
                transcribed_audio_text = audio_result.get("transcription", "")
                if transcribed_audio_text:
                    st.info(f"የተሰማው ድምፅ: **{transcribed_audio_text}**")
                else:
                    st.warning("ምንም ድምፅ አልተሰማም።")

    # --- Text input (alternative) ---
    typed_text = st.text_input("✏️ ወይም እዚህ ይተይቡ (Or type here)", key="typed_command")
    process_text = st.button("➡️ ትእዛዝ አስፈጽም (Process Text Command)")

    # Determine which result to use: audio has priority if available; else text if button pressed
    if result_from_audio is not None:
        result = result_from_audio
        final_command = transcribed_audio_text or ""
        source_label = "🎧 Gemini Audio"
    elif process_text:
        with st.spinner("🧠 ትእዛዝዎን በመተንተን ላይ... (Understanding your command...)"):
            result = understand_command(typed_text)
        final_command = typed_text
        source_label = "📝 Text Input"
    else:
        result = None
        final_command = ""
        source_label = ""

    if result is not None:
        intent = result.get("intent", "UNKNOWN")
        params = result.get("parameters", {})
        ai_response = result.get("response_amharic", "")
        source = result.get("source", "unknown")
        model_used = result.get("model_used")

        if source in ("gemini", "gemini_audio"):
            badge_label = f"🧠 Gemini AI ({model_used})" if model_used else "🧠 Gemini AI"
        elif source == "fallback":
            badge_label = "🔁 Local Fallback"
        else:
            badge_label = "—"
        st.markdown(f"<span class='badge-ai'>{badge_label}</span>", unsafe_allow_html=True)

        with st.expander("🔍 Debug: NLU Result"):
            st.json(result)

        st.markdown("---")

        if not final_command and not transcribed_audio_text:
            st.markdown(f"<span class='badge-error'>{ai_response}</span>", unsafe_allow_html=True)

        elif intent == "GREETING":
            st.markdown("<span class='badge-success'>👋 ሰላምታ ተገኝቷል</span>", unsafe_allow_html=True)
            st.markdown(ai_response)

        elif intent == "CHECK_BALANCE":
            st.markdown("<span class='badge-success'>✅ ቀሪ ሂሳብ ተገኝቷል</span>", unsafe_allow_html=True)
            if ai_response:
                st.markdown(f"🗣️ *{ai_response}*")
            st.markdown(check_balance_text())

        elif intent == "BUY_PACKAGE":
            st.info(f"🗣️ {ai_response}" if ai_response else
                    "📦 ጥቅል መግዛት ይፈልጋሉ። እባክዎ ከ«📦 የፓኬጅ ዝርዝሮች» ትር ውስጥ ይምረጡ።")
            if params.get("package_type"):
                st.caption(f"🔎 የተጠቀሰ ዓይነት፦ {params['package_type']} — ከፓኬጅ ትር ውስጥ ተመሳሳይ ጥቅል ይምረጡ።")

        elif intent == "TRANSFER_TELEBIRR":
            st.info(f"🗣️ {ai_response}" if ai_response else
                    "💸 ገንዘብ ማስተላለፍ ይፈልጋሉ። እባክዎ ከ«💸 ቴሌብር ማስተላለፊያ» ትር ውስጥ ዝርዝሮችን ያስገቡ።")
            # Pre-fill the transfer tab if phone/amount extracted
            if params.get("phone_number"):
                st.session_state.prefill_phone = str(params["phone_number"])
            if params.get("amount"):
                st.session_state.prefill_amount = str(params["amount"])
            if params.get("phone_number") or params.get("amount"):
                st.caption("✅ ስልክ ቁጥር/መጠን ወደ ቴሌብር ትር ተቀድቷል።")

        else:  # UNKNOWN
            st.warning(ai_response or (
                "😕 ይቅርታ፣ በትክክል አልተረዳሁትም። እባክዎ በሚከተለው መልኩ ይሞክሩ፦\n\n"
                "- «ቀሪ ሂሳቤን አሳየኝ» (ለቀሪ ሂሳብ)\n"
                "- «ጥቅል መግዛት እፈልጋለሁ» (ለፓኬጅ ግዢ)\n"
                "- «ገንዘብ ወደ ቴሌብር ላክ» (ለቴሌብር ማስተላለፍ)"
            ))

        if "error" in result:
            st.caption(f"⚠️ All Gemini models failed, used fallback. Details: {result['error']}")


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

    phone_number = st.text_input("📱 የተቀባይ ስልክ ቁጥር", value=st.session_state.prefill_phone,
                                  placeholder="0912345678")
    amount = st.text_input("💰 የሚላከው መጠን (ብር)", value=st.session_state.prefill_amount,
                            placeholder="ለምሳሌ 100")

    if st.button("➡️ ገንዘብ ላክ (Send Money)"):
        success, msg = telebirr_transfer(phone_number, amount)
        if success:
            st.markdown("<span class='badge-success'>✅ ግብይት ተሳክቷል!</span>", unsafe_allow_html=True)
            st.markdown(msg)
            st.session_state.prefill_phone = ""
            st.session_state.prefill_amount = ""
            st.rerun()
        else:
            st.markdown("<span class='badge-error'>❌ ግብይት አልተሳካም</span>", unsafe_allow_html=True)
            st.markdown(msg)


# =========================================================
# ACTIVITY HISTORY
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
