"""
Telebirr FraudShield AI — የቴሌብር ደህንነት መርማሪ
Receipt-screenshot forensic analyzer. Backend model access is fully
white-labeled in the UI — no vendor/model/protocol names are ever shown
to the user.
Run with: streamlit run app.py
"""

import streamlit as st
import os
from PIL import Image

try:
    import google.generativeai as genai
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
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "")


_BACKEND_KEY = _get_backend_key()
SYSTEM_READY = bool(_BACKEND_KEY) and SDK_AVAILABLE

_model = None
if SYSTEM_READY:
    try:
        genai.configure(api_key=_BACKEND_KEY)
        _model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception:
        SYSTEM_READY = False
        _model = None

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


def _analyze_receipt(uploaded_file):
    """
    Sends the receipt image, alongside the forensic prompt, to the backend
    for analysis. Any failure is raised up to the caller, which shows one
    clean Amharic error message with no technical detail exposed.
    """
    image = Image.open(uploaded_file)
    response = _model.generate_content([FORENSIC_SYSTEM_PROMPT, image])
    return response.text.strip()


def _parse_verdict_and_score(analysis_text):
    """
    Best-effort extraction of a headline verdict label and a numeric risk
    score (0-100) from the free-form Amharic analysis text, for the
    st.metric summary cards.
    """
    import re
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

            except Exception:
                st.error(GENERIC_ERROR_MESSAGE)

st.markdown("---")
st.caption(
    "⚠️ ማሳሰቢያ: ይህ የራስ-ሰር ትንተና መሳሪያ ሲሆን ውጤቱ ጠቋሚ እንጂ የመጨረሻ ማረጋገጫ አይደለም። "
    "ትልቅ ግብይቶችን ከማጽደቅዎ በፊት በተጨማሪ በራስዎ እንዲያረጋግጡ እንመክራለን።"
)
