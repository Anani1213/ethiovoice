"""
Telebirr FraudShield AI (Vision Edition)
-----------------------------------------
Streamlit application that forensically inspects uploaded Telebirr
transaction receipt / SMS confirmation screenshots for signs of
tampering, and reports the result to the user in Amharic.

Setup:
    pip install streamlit google-generativeai pillow

    Add to .streamlit/secrets.toml:
        GEMINI_API_KEY = "your-key-here"

    Run:
        streamlit run app.py
"""

import json
import logging

import streamlit as st
from PIL import Image
import google.generativeai as genai

# --------------------------------------------------------------------------
# Logging (developer-facing only — never surfaced in the UI)
# --------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fraudshield")

# --------------------------------------------------------------------------
# Page configuration
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Telebirr FraudShield AI",
    page_icon="🛡️",
    layout="wide",
)

st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stApp {
            background-color: #f6f9f7;
        }
        h1, h2, h3 {
            color: #00753A;
        }
        div.stButton > button {
            background-color: #00873E;
            color: white;
            border-radius: 10px;
            font-weight: 600;
            padding: 0.6rem 1.2rem;
            border: none;
        }
        div.stButton > button:hover {
            background-color: #00692F;
            color: white;
        }
        div.stButton > button:disabled {
            background-color: #a9b8ae;
            color: #f0f0f0;
        }
        [data-testid="stMetricValue"] {
            color: #00753A;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Backend configuration (internal only — never rendered in the UI)
# --------------------------------------------------------------------------
_MODEL_FALLBACK_CHAIN = [
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
]

_FORENSIC_SYSTEM_PROMPT = """
You are a forensic document analyst specializing in detecting fraudulent,
edited, or AI-generated Ethiopian Telebirr mobile money transaction
receipts and SMS confirmation screenshots.

Carefully inspect the uploaded image for signs of tampering, including:

1. Font consistency — whether all text (amounts, names, dates, labels)
   uses the same font, weight, and rendering style throughout the image,
   with no mismatched or blurry text blocks.
2. Number alignment and spacing — whether digits in the amount, phone
   number, and transaction ID are evenly spaced, properly aligned, and
   consistent with genuine Telebirr formatting.
3. Telebirr logo and brand element accuracy — the logo shape, color, and
   placement compared to authentic Telebirr receipts.
4. Transaction ID structure — whether the transaction ID follows a
   plausible Telebirr ID format and character pattern.
5. Signs of digital editing — cloning artifacts, mismatched pixel noise,
   inconsistent shadows/highlights, misaligned layers, or copy-paste
   evidence typical of image editing tools.

Respond with ONLY a valid JSON object (no markdown fences, no extra
commentary, no text before or after it) in exactly this structure:

{
  "verdict": "real" or "fake",
  "risk_score": <integer 0-100, where 0 = definitely genuine and
                 100 = definitely fraudulent>,
  "reasons": ["<Amharic reason 1>", "<Amharic reason 2>", "..."]
}

Every string inside "reasons" must be written in clear, professional
Amharic, explaining the specific forensic evidence observed in the
image. Do not include any text outside the JSON object.
"""


def _load_backend_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None


_backend_key = _load_backend_key()
_SERVICE_READY = bool(_backend_key)

if _SERVICE_READY:
    try:
        genai.configure(api_key=_backend_key)
    except Exception as exc:
        logger.error("Backend configuration failed: %s", exc)
        _SERVICE_READY = False


def _clean_json_block(raw_text: str) -> str:
    """Strip markdown code fences the model may wrap the JSON in."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _clamp_score(value) -> int:
    """Coerce a risk score into a safe 0-100 integer."""
    try:
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return 50


def run_forensic_analysis(image: Image.Image) -> dict:
    """
    Run the forensic inspection on the uploaded image.

    Silently tries each model in the fallback chain until one returns a
    usable result. Raises RuntimeError if every attempt fails — callers
    must catch this and show a clean, user-facing message.
    """
    if not _SERVICE_READY:
        raise RuntimeError("service_unavailable")

    last_error = None
    for model_name in _MODEL_FALLBACK_CHAIN:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content([_FORENSIC_SYSTEM_PROMPT, image])
            payload = _clean_json_block(response.text)
            result = json.loads(payload)

            verdict = str(result.get("verdict", "")).strip().lower()
            if verdict not in ("real", "fake"):
                raise ValueError(f"unexpected verdict value: {verdict!r}")

            reasons = result.get("reasons", [])
            if not isinstance(reasons, list) or not reasons:
                raise ValueError("missing or empty reasons list")

            return {
                "verdict": verdict,
                "risk_score": _clamp_score(result.get("risk_score", 50)),
                "reasons": [str(r) for r in reasons],
            }
        except Exception as exc:
            logger.warning("Inspection attempt failed (%s): %s", model_name, exc)
            last_error = exc
            continue

    raise RuntimeError("analysis_failed") from last_error


# --------------------------------------------------------------------------
# UI helpers
# --------------------------------------------------------------------------
def render_verdict(result: dict) -> None:
    verdict = result["verdict"]
    risk_score = result["risk_score"]
    reasons = result["reasons"]

    col1, col2 = st.columns([2, 1])
    with col1:
        if verdict == "real":
            st.success("🟢 እውነተኛ የቴሌብር ደረሰኝ")
        else:
            st.error("🔴 የትስስር/የተቀየረ ሀሰተኛ ደረሰኝ")
    with col2:
        st.metric(label="የማጭበርበር አደጋ መጠን", value=f"{risk_score}%")

    st.markdown("#### 🔎 ዝርዝር የምርመራ ውጤቶች")
    for reason in reasons:
        st.markdown(f"- {reason}")


_DEMO_RESULT = {
    "verdict": "fake",
    "risk_score": 87,
    "reasons": [
        "በገንዘብ መጠኑ ፊደላት ዙሪያ ግልጽ ያልሆነ የፒክሰል መደበላለቅ ታይቷል፣ ይህም የአርትዖት ምልክት ነው።",
        "የግብይት መለያ ቁጥር አወቃቀር ከመደበኛው የቴሌብር ቅርጸት ጋር አይመሳሰልም።",
        "የቴሌብር አርማ ቀለም ከትክክለኛው ስሪት ጋር ሲነጻጸር ልዩነት ያሳያል።",
        "የቀን እና የሰዓት ቁጥሮች አሰላለፍ ያልተስተካከለ ሆኖ ተገኝቷል።",
    ],
}


def render_demo_section() -> None:
    with st.expander("🧪 የናሙና ትንታኔ ውጤት ይመልከቱ (ለሙከራ)"):
        st.caption("ከዚህ በታች ያለው ውጤት ምንም ምስል ሳይሰቀል የሚታይ የናሙና ማሳያ ብቻ ነው።")
        render_verdict(_DEMO_RESULT)


# --------------------------------------------------------------------------
# Main UI
# --------------------------------------------------------------------------
st.title("Telebirr FraudShield AI")
st.subheader("የቴሌብር ደህንነት መርማሪ")
st.write(
    "የቴሌብር ደረሰኝ ወይም የኤስኤምኤስ ቅጽበታዊ ገጽ እይታ ይስቀሉ፤ ስርዓቱ ምስሉን በዲጂታል ቅኝት መርምሮ "
    "ትክክለኛነቱን ወይም መቀየሩን ይነግርዎታል።"
)

if not _SERVICE_READY:
    st.warning(
        "የደህንነት ምርመራ አገልግሎት በአሁኑ ጊዜ ሙሉ በሙሉ ማዋቀር አልተጠናቀቀም፤ "
        "እባክዎ ከስርዓት አስተዳዳሪ ጋር ያረጋግጡ።"
    )

render_demo_section()
st.markdown("---")

uploaded_file = st.file_uploader(
    "ደረሰኝ ወይም ኤስኤምኤስ ምስል ይስቀሉ",
    type=["png", "jpg", "jpeg"],
)

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "_last_file_signature" not in st.session_state:
    st.session_state._last_file_signature = None

if uploaded_file is not None:
    file_signature = (uploaded_file.name, uploaded_file.size)
    if st.session_state._last_file_signature != file_signature:
        st.session_state.analysis_result = None
        st.session_state._last_file_signature = file_signature

    image = None
    try:
        image = Image.open(uploaded_file).convert("RGB")
    except Exception as exc:
        logger.error("Failed to open uploaded image: %s", exc)
        st.error(
            "የምስል ምርመራው ላይ ጊዜያዊ ችግር አጋጥሟል፤ እባክዎ ምስሉ ግልጽ መሆኑን አረጋግጠው ድጋሚ ይሞክሩ።"
        )

    if image is not None:
        col_img, col_action = st.columns([1, 1])

        with col_img:
            st.image(image, caption="የተሰቀለው ምስል", use_container_width=True)
            st.caption("ምስሉ ለደህንነት ምርመራ ዝግጁ ነው")

        with col_action:
            st.write("")
            analyze_clicked = st.button(
                "🔍 ደረሰኙን መርምር (Analyze Receipt)",
                disabled=not _SERVICE_READY,
                use_container_width=True,
            )

            if analyze_clicked:
                with st.spinner("የቴሌብር ሴኩሪቲ ሲስተም ምስሉን በመመርመር ላይ ነው..."):
                    try:
                        result = run_forensic_analysis(image)
                        st.session_state.analysis_result = result
                    except Exception as exc:
                        logger.error("Forensic analysis failed: %s", exc)
                        st.session_state.analysis_result = None
                        st.error(
                            "የምስል ምርመራው ላይ ጊዜያዊ ችግር አጋጥሟል፤ "
                            "እባክዎ ምስሉ ግልጽ መሆኑን አረጋግጠው ድጋሚ ይሞክሩ።"
                        )

    if st.session_state.analysis_result:
        st.markdown("---")
        render_verdict(st.session_state.analysis_result)

st.markdown("---")
st.caption(
    "ይህ ስርዓት የመጀመሪያ ደረጃ ግንዛቤ ለመስጠት የተዘጋጀ እንጂ የመጨረሻ ውሳኔ ተደርጎ ሊወሰድ አይገባም።"
)
