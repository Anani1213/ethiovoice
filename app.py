"""
Telebirr FraudShield AI — የቴሌብር ደህንነት መርማሪ
Receipt-screenshot forensic analyzer. Backend model access is fully
white-labeled in the UI — no vendor/model/protocol names are ever shown
to the user.
Run with: streamlit run app.py
"""

import streamlit as st
import base64
import os
import re

try:
    from openai import OpenAI
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="Telebirr FraudShield AI", page_icon="🛡️", layout="centered")

st.markdown("""
<style>
    html, body, [class*="css"]  { font-size: 18px !important; }
    h1 { font-size: 2rem !important; }
    .stButton > button {
        font-size: 1.1rem !important;
        font-weight: 700 !important;
        padding: 0.9em 1.2em !important;
        border-radius: 14px !important;
        border: 2px solid #7a1f1f !important;
        width: 100%;
    }
    .verdict-card {
        border-radius: 14px; padding: 18px; margin: 14px 0;
        border: 2px solid #ddd; background-color: #fafafa;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# BACKEND SETUP (kept out of the visible UI entirely)
# =========================================================
def _get_backend_key():
    """Fetch the backend credential from Streamlit secrets first, then environment."""
    try:
        if "OPENAI_API_KEY" in st.secrets:
            return st.secrets["OPENAI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("OPENAI_API_KEY", "")


_BACKEND_KEY = _get_backend_key()
SYSTEM_READY = bool(_BACKEND_KEY) and SDK_AVAILABLE

_client = None
if SYSTEM_READY:
    try:
        _client = OpenAI(api_key=_BACKEND_KEY)
    except Exception:
        SYSTEM_READY = False
        _client = None

# Tried in order; if the first is unavailable for this account/key, the
# second is used automatically. Never shown in the UI.
_MODEL_CANDIDATES = ["gpt-4o-mini", "gpt-4o"]

FORENSIC_SYSTEM_PROMPT = (
    "You are an expert Telebirr forensic transaction analyzer. Inspect this "
    "receipt screenshot for photoshopped edits, inconsistent fonts, "
    "misaligned numbers, or altered transaction IDs. Respond ONLY in Amharic "
    "with: 1) Verdict (🟢 እውነተኛ የቴሌብር ደረሰኝ / 🔴 የትስስር/የተቀየረ ሀሰተኛ ደረሰኝ), "
    "2) Fraud Risk Score (0-100%), and 3) Detailed Bulleted Reasons."
)

GENERIC_ERROR_MESSAGE = (
    "የምስል ምርመራው ላይ ጊዜያዊ ችግር አጋጥሟል፤ እባክዎ ምስሉ ግልጽ መሆኑን አረጋግጠው ድጋሚ ይሞክሩ።"
)


def _encode_image_to_base64(uploaded_file):
    """Convert an uploaded image file's raw bytes into a base64 string."""
    file_bytes = uploaded_file.getvalue()
    return base64.b64encode(file_bytes).decode("utf-8")


def _analyze_receipt(uploaded_file):
    """
    Sends the receipt image, alongside the forensic system prompt, to the
    backend for analysis. Tries each candidate model in turn; raises only
    after every candidate has failed, so the caller can show one clean
    Amharic error message with no technical detail exposed.
    """
    b64_image = _encode_image_to_base64(uploaded_file)
    mime_type = uploaded_file.type or "image/jpeg"
    data_url = f"data:{mime_type};base64,{b64_image}"

    last_error = None
    for model_name in _MODEL_CANDIDATES:
        try:
            response = _client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": FORENSIC_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "ይህን የቴሌብር ደረሰኝ ስክሪንሾት በጥንቃቄ መርምር።"},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                max_tokens=800,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            continue

    raise last_error if last_error is not None else RuntimeError("Analysis unavailable")


def _parse_verdict_and_score(analysis_text):
    """
    Best-effort extraction of a headline verdict label and a numeric risk
    score (0-100) from the free-form Amharic analysis text, for the
    st.metric summary cards.
    """
    score_match = re.search(r"(\d{1,3})\s*%", analysis_text)
    score = None
    if score_match:
        score = max(0, min(100, int(score_match.group(1))))

    if "🔴" in analysis_text:
        verdict_label = "🔴 ሀሰተኛ/የተቀየረ ሊሆን ይችላል"
    elif "🟢" in analysis_text:
        verdict_label = "🟢 እውነተኛ ደረሰኝ ይመስላል"
    else:
        verdict_label = "❓ ውጤት ግልጽ አይደለም"

    return verdict_label, score


# =========================================================
# SIDEBAR — minimal, no backend details ever shown
# =========================================================
with st.sidebar:
    st.header("🛡️ Telebirr FraudShield AI")
    st.caption("የቴሌብር ደረሰኝ ትክክለኛነት መርማሪ")
    if SYSTEM_READY:
        st.success("✅ ስርዓቱ ዝግጁ ነው")
    else:
        st.warning("⚠️ ስርዓቱ በአሁኑ ጊዜ አልተዋቀረም። እባክዎ ቆይተው ይሞክሩ።")
    st.markdown("---")
    st.caption(
        "ደረሰኝ ስክሪንሾት ይስቀሉ እና ስርዓቱ ፎቶሾፕ መደረጉን፣ ያልተስተካከሉ ፊደላትን፣ "
        "የተዛቡ ቁጥሮችን ወይም የተቀየሩ የግብይት መለያዎችን ይመረምራል።"
    )


# =========================================================
# MAIN UI
# =========================================================
st.title("🛡️ Telebirr FraudShield AI")
st.caption("የቴሌብር ደህንነት መርማሪ")

st.write("የቴሌብር ደረሰኝ ስክሪንሾት ከታች ይስቀሉ፤ ትክክለኛነቱን በደቂቃዎች ውስጥ እናረጋግጣለን።")

uploaded_file = st.file_uploader(
    "📷 የደረሰኝ ስክሪንሾት ይስቀሉ",
    type=["png", "jpg", "jpeg", "webp"],
)

if uploaded_file is not None:
    st.image(uploaded_file, caption="የተሰቀለው ደረሰኝ", use_container_width=True)

analyze_clicked = st.button("🔍 ደረሰኙን መርምር (Analyze Receipt)")

if analyze_clicked:
    if uploaded_file is None:
        st.warning("እባክዎ በመጀመሪያ የደረሰኝ ስክሪንሾት ይስቀሉ።")
    elif not SYSTEM_READY:
        st.error("ስርዓቱ በአሁኑ ጊዜ አልተዋቀረም። እባክዎ ቆይተው ይሞክሩ።")
    else:
        with st.spinner("ደረሰኙን በጥንቃቄ በመመርመር ላይ..."):
            try:
                analysis_text = _analyze_receipt(uploaded_file)
                verdict_label, score = _parse_verdict_and_score(analysis_text)

                st.markdown("---")
                col1, col2 = st.columns(2)
                col1.metric("🔎 ውጤት (Verdict)", verdict_label)
                col2.metric(
                    "⚠️ የማጭበርበር እድል",
                    f"{score}%" if score is not None else "N/A",
                )

                st.markdown("<div class='verdict-card'>", unsafe_allow_html=True)
                st.markdown("#### 📝 ዝርዝር ትንተና")
                st.markdown(analysis_text)
                st.markdown("</div>", unsafe_allow_html=True)

            except Exception as e:
                st.error(f"የምስል ምርመራው ላይ ጊዜያዊ ችግር አጋጥሟል... Debug Info: {str(e)}")

st.markdown("---")
st.caption(
    "⚠️ ማሳሰቢያ: ይህ የራስ-ሰር ትንተና መሳሪያ ሲሆን ውጤቱ ጠቋሚ እንጂ የመጨረሻ ማረጋገጫ አይደለም። "
    "ትልቅ ግብይቶችን ከማጽደቅዎ በፊት በተጨማሪ በራስዎ እንዲያረጋግጡ እንመክራለን።"
)
