"""
Telebirr FraudShield AI - የቴሌብር ደህንነት መርማሪ
Vision Edition

Run:
    pip install streamlit pillow google-generativeai
    streamlit run app.py

Create:
    .streamlit/secrets.toml

With:
    GEMINI_API_KEY = "YOUR_SECRET_KEY"
"""

import re
from typing import Optional, Tuple

import streamlit as st
from PIL import Image, UnidentifiedImageError
import google.generativeai as genai


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Telebirr FraudShield AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CONSTANTS
# ============================================================

USER_ERROR_MESSAGE = (
    "የምስል ምርመራው ላይ ጊዜያዊ ችግር አጋጥሟል፤ "
    "እባክዎ ምስሉ ግልጽ መሆኑን አረጋግጠው ድጋሚ ይሞክሩ።"
)

# Internal-only model fallback order.
# These values are NEVER rendered in the UI.
MODEL_CANDIDATES = (
    "gemini-1.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash",
)

FORENSIC_PROMPT = """
You are an expert Telebirr forensic transaction analyzer.

Analyze the supplied Telebirr transaction receipt or transaction
SMS screenshot as a visual forensic investigator.

Carefully inspect the image for possible manipulation, including:

1. Font consistency
   - Compare font family, weight, size, spacing and rendering.
   - Look for text that appears pasted or replaced.

2. Numbers and amount alignment
   - Inspect digit spacing, baseline alignment and positioning.
   - Check whether amounts appear visually inconsistent with surrounding text.

3. Telebirr branding
   - Inspect the apparent Telebirr logo, colors, proportions,
     spacing and visual consistency.
   - Do not claim official authenticity solely from the presence of a logo.

4. Transaction ID
   - Inspect the transaction/reference ID structure.
   - Look for inconsistent character shapes, spacing, positioning,
     sharpness or evidence of replacement.

5. Photoshop or manual editing indicators
   - Look for pasted regions, inconsistent compression,
     halos, edges, duplicated pixels, different sharpness,
     inconsistent backgrounds, suspicious spacing and layering artifacts.

6. AI-generated/manipulated visual artifacts
   - Look for unnatural text rendering, malformed characters,
     inconsistent geometry, repeated patterns and other visual anomalies.

7. Overall consistency
   - Compare all visible sections of the screenshot against one another.
   - Consider image resolution and compression before making a conclusion.

IMPORTANT LIMITATIONS:
- This is a visual forensic assessment only.
- A screenshot cannot prove that a real financial transaction occurred.
- Do not claim to have verified the transaction against a financial database.
- Do not invent transaction details that are not visible.
- If evidence is inconclusive, say so clearly.
- Do not automatically classify an image as fraudulent merely because
  it has been compressed, resized or photographed from a screen.

Return ONLY a structured report in clear Amharic using this format:

VERDICT: [REAL or FAKE]

RISK: [0-100]%

REASONS:
- [Detailed Amharic forensic reason]
- [Detailed Amharic forensic reason]
- [Detailed Amharic forensic reason]
- [Detailed Amharic forensic reason]

CONFIDENCE: [0-100]%

LIMITATIONS:
- [Short Amharic limitation]

For VERDICT use:
REAL = 🟢 እውነተኛ የቴሌብር ደረሰኝ
FAKE = 🔴 የትስስር/የተቀየረ ሀሰተኛ ደረሰኝ

Keep the forensic reasons specific to visible evidence.
"""


# ============================================================
# STYLING
# ============================================================

st.markdown(
    """
    <style>
        .main {
            padding-top: 1rem;
        }

        .hero {
            padding: 1.8rem 2rem;
            border-radius: 20px;
            background: linear-gradient(
                135deg,
                #087f5b 0%,
                #07553f 100%
            );
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
        }

        .hero h1 {
            margin: 0;
            font-size: 2.25rem;
            line-height: 1.25;
        }

        .hero p {
            margin-top: 0.65rem;
            margin-bottom: 0;
            font-size: 1.05rem;
            opacity: 0.94;
        }

        .security-card {
            padding: 1.25rem;
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 16px;
            margin-bottom: 1rem;
        }

        .real-card {
            padding: 1.2rem;
            border-radius: 14px;
            border: 1px solid #16a34a;
            background: rgba(22, 163, 74, 0.08);
        }

        .fake-card {
            padding: 1.2rem;
            border-radius: 14px;
            border: 1px solid #dc2626;
            background: rgba(220, 38, 38, 0.08);
        }

        .warning-card {
            padding: 1.2rem;
            border-radius: 14px;
            border: 1px solid #ca8a04;
            background: rgba(202, 138, 4, 0.08);
        }

        .footer {
            text-align: center;
            padding: 2rem 0 1rem 0;
            opacity: 0.65;
            font-size: 0.85rem;
        }

        div[data-testid="stMetric"] {
            border-radius: 12px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SAFE BACKEND INITIALIZATION
# ============================================================

@st.cache_resource(show_spinner=False)
def initialize_security_engine():
    """
    Initialize the analysis engine.

    All backend details remain internal.
    No backend/model names are returned to the UI.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]

        if not api_key or not str(api_key).strip():
            return None

        genai.configure(api_key=str(api_key).strip())

        return True

    except Exception:
        return None


def get_model_safely():
    """
    Try supported model candidates silently.

    Returns the first model that initializes successfully.
    Never exposes internal model names to the user.
    """
    if initialize_security_engine() is None:
        return None

    for model_name in MODEL_CANDIDATES:
        try:
            model = genai.GenerativeModel(model_name)

            # Basic object validation without making a network request.
            if model is not None:
                return model

        except Exception:
            continue

    return None


# ============================================================
# IMAGE VALIDATION
# ============================================================

def load_uploaded_image(uploaded_file) -> Optional[Image.Image]:
    """
    Safely open and normalize an uploaded image.
    """
    try:
        if uploaded_file is None:
            return None

        image = Image.open(uploaded_file)

        # Force image data to be fully loaded while the uploaded
        # file object is still available.
        image.load()

        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        return image

    except (UnidentifiedImageError, OSError, ValueError):
        return None

    except Exception:
        return None


# ============================================================
# AI ANALYSIS
# ============================================================

def perform_analysis(
    model,
    image: Image.Image,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Analyze an image with the configured vision engine.

    Returns:
        (result_text, error)
    """

    if model is None:
        return None, USER_ERROR_MESSAGE

    try:
        response = model.generate_content(
            [
                FORENSIC_PROMPT,
                image,
            ],
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1400,
            },
        )

        if response is None:
            return None, USER_ERROR_MESSAGE

        try:
            result_text = response.text
        except Exception:
            result_text = None

        if not result_text or not result_text.strip():
            return None, USER_ERROR_MESSAGE

        return result_text.strip(), None

    except Exception:
        # Never expose backend exception details.
        return None, USER_ERROR_MESSAGE


# ============================================================
# RESULT PARSING
# ============================================================

def clamp_percentage(value: int) -> int:
    return max(0, min(100, value))


def extract_risk_score(text: str) -> Optional[int]:
    """
    Extract the risk percentage safely.
    """
    if not text:
        return None

    patterns = (
        r"RISK\s*:\s*?\s*(\d{1,3})\s*%?",
        r"RISK SCORE\s*:\s*\[?\s*(\d{1,3})\s*%?",
        r"የማጭበርበር.*?(\d{1,3})\s*%",
    )

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            try:
                return clamp_percentage(int(match.group(1)))
            except (ValueError, TypeError):
                continue

    return None


def extract_confidence(text: str) -> Optional[int]:
    """
    Extract confidence percentage if supplied.
    """
    if not text:
        return None

    pattern = r"CONFIDENCE\s*:\s*\[?\s*(\d{1,3})\s*%?"

    match = re.search(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    if match:
        try:
            return clamp_percentage(int(match.group(1)))
        except (ValueError, TypeError):
            return None

    return None


def detect_verdict(text: str) -> str:
    """
    Determine verdict from structured output.
    """
    if not text:
        return "⚪ ምርመራው ውጤት አልተገኘም"

    upper_text = text.upper()

    # Strong fake indicators first.
    if (
        "VERDICT: [FAKE]" in upper_text
        or "VERDICT: FAKE" in upper_text
        or "🔴" in text
    ):
        return "🔴 የትስስር/የተቀየረ ሀሰተኛ ደረሰኝ"

    if (
        "VERDICT: [REAL]" in upper_text
        or "VERDICT: REAL" in upper_text
        or "🟢" in text
    ):
        return "🟢 እውነተኛ የቴሌብር ደረሰኝ"

    return "⚪ የምርመራ ውጤቱ የተወሰነ አይደለም"


def clean_report(text: str) -> str:
    """
    Remove structured metadata from the report body.
    """
    if not text:
        return ""

    cleaned = text

    patterns = (
        r"VERDICT\s*:\s*\[?.*??\s*",
        r"RISK\s*:\s*?.*??\s*",
        r"CONFIDENCE\s*:\s*?.*??\s*",
    )

    for pattern in patterns:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

    return cleaned.strip()


# ============================================================
# RESULT DISPLAY
# ============================================================

def display_result(result_text: str):
    """
    Render forensic result using professional security UI.
    """

    verdict = detect_verdict(result_text)
    risk = extract_risk_score(result_text)
    confidence = extract_confidence(result_text)

    st.markdown("## 🔎 የደህንነት ምርመራ ውጤት")

    verdict_col, risk_col, confidence_col = st.columns(3)

    with verdict_col:
        st.markdown("### ውሳኔ")

        if verdict.startswith("🟢"):
            st.success(verdict)
        elif verdict.startswith("🔴"):
            st.error(verdict)
        else:
            st.warning(verdict)

    with risk_col:
        st.markdown("### የአደጋ ደረጃ")

        if risk is None:
            st.metric(
                label="Risk Score",
                value="—",
            )
        else:
            st.metric(
                label="Risk Score",
                value=f"{risk}%",
            )

            if risk >= 70:
                st.error("ከፍተኛ የማጭበርበር አደጋ")
            elif risk >= 40:
                st.warning("መካከለኛ የማጭበርበር አደጋ")
            else:
                st.success("ዝቅተኛ የማጭበርበር አደጋ")

    with confidence_col:
        st.markdown("### የምርመራ እምነት")

        if confidence is None:
            st.metric(
                label="Confidence",
                value="—",
            )
        else:
            st.metric(
                label="Confidence",
                value=f"{confidence}%",
            )

    st.divider()

    st.markdown("### 📋 ዝርዝር የForensic ምርመራ")

    report = clean_report(result_text)

    if report:
        st.markdown(report)
    else:
        st.info(
            "ዝርዝር የምርመራ ማብራሪያ አልተገኘም።"
        )

    st.warning(
        "⚠️ ይህ የምስል ምርመራ ውጤት ብቻ ነው። "
        "ከደረሰኝ ምስል ብቻ እውነተኛ ግብይት መፈጸሙን "
        "በትክክል ማረጋገጥ አይቻልም።"
    )


# ============================================================
# DEMO DATA
# ============================================================

DEMO_RESULT = """
VERDICT: [REAL]

RISK: 12%

REASONS:
- በምስሉ ውስጥ የጽሁፍ ፎንት፣ መጠንና የፊደላት አቀማመጥ
  በአብዛኛው ወጥ ሆኖ ይታያል።
- የቁጥሮች አቀማመጥና baseline በተለያዩ ክፍሎች
  መካከል የሚታይ ከፍተኛ ልዩነት አልታየም።
- የTransaction ID አቀማመጥ ከተቀሩት የጽሁፍ ክፍሎች
  ጋር ተመጣጣኝ ይመስላል።
- በAmount አካባቢ ግልጽ የተለጠፈ ወይም የተቀየረ
  ክፍል ምልክት አልታየም።
- የምስሉ ጥራትና compression በአብዛኛው ወጥ ነው።

CONFIDENCE: 82%

LIMITATIONS:
- ይህ የvisual forensic screening ነው፤ የግብይት መኖሩን
  ከኦፊሴላዊ የግብይት መዝገብ ጋር አያረጋግጥም።
"""


# ============================================================
# HEADER
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>
            Telebirr FraudShield AI -
            የቴሌብር ደህንነት መርማሪ
        </h1>
        <p>
            የግብይት ደረሰኞችን ምስላዊ የማጭበርበር
            ምልክቶች ለመለየት የተዘጋጀ የደህንነት መርማሪ።
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("## 🛡️ FraudShield AI")

    st.markdown(
        """
        ### የደህንነት ምርመራ

        የTelebirr ደረሰኝ ወይም SMS screenshot
        በመጫን የምስል ማጭበርበር ምልክቶችን
        ለመመርመር ይጠቀሙ።
        """
    )

    st.divider()

    st.markdown("### 🔍 የሚመረመሩ ነገሮች")

    st.markdown(
        """
        - ፎንት ተመሳሳይነት
        - የቁጥሮች አቀማመጥ
        - የግብይት መለያ ቁጥር
        - የደረሰኝ አቀራረብ
        - የTelebirr ሎጎ ምስላዊ ተመሳሳይነት
        - የቀለም ልዩነቶች
        - የPhotoshop ምልክቶች
        - የምስል ማጭበርበር ምልክቶች
        """
    )

    st.divider()

    st.caption(
        "Telebirr FraudShield AI • Vision Edition"
    )


# ============================================================
# INTRO
# ============================================================

left_intro, right_intro = st.columns([2, 1])

with left_intro:

    st.markdown("## 🔎 ደረሰኙን ይመርምሩ")

    st.write(
        "የTelebirr የግብይት ደረሰኝ ወይም SMS screenshot "
        "ይጫኑ። ስርዓቱ የምስሉን የጽሁፍ፣ ቁጥሮች፣ "
        "አቀማመጥ፣ ሎጎ እና የማስተካከያ ምልክቶች "
        "ይመረምራል።"
    )

with right_intro:

    st.markdown("### 📁 የሚደገፉ ፎርማቶች")

    st.metric(
        label="Image Formats",
        value="PNG / JPG / JPEG",
    )


# ============================================================
# UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "📤 የTelebirr ደረሰኝ ወይም SMS Screenshot ይጫኑ",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=False,
    help="PNG, JPG ወይም JPEG ምስል ይምረጡ።",
)


# ============================================================
# UPLOAD PROCESSING
# ============================================================

if uploaded_file is not None:

    image = load_uploaded_image(uploaded_file)

    if image is None:

        st.error(USER_ERROR_MESSAGE)

    else:

        st.success(
            "ምስሉ ለደህንነት ምርመራ ዝግጁ ነው።"
        )

        st.divider()

        image_col, details_col = st.columns([1.25, 1])

        with image_col:

            st.markdown("### 🖼️ የተጫነው ምስል")

            st.image(
                image,
                caption=uploaded_file.name,
                use_container_width=True,
            )

        with details_col:

            st.markdown("### 📄 የምስል መረጃ")

            width, height = image.size

            info1, info2 = st.columns(2)

            with info1:
                st.metric(
                    label="ስፋት",
                    value=f"{width}px",
                )

            with info2:
                st.metric(
                    label="ቁመት",
                    value=f"{height}px",
                )

            st.info(
                "የተሻለ ውጤት ለማግኘት ጽሁፎችና ቁጥሮች "
                "ግልጽ የሆኑበትን ምስል ይጠቀሙ።"
            )

        st.divider()

        if st.button(
            "🔍 ደረሰኙን መርምር (Analyze Receipt)",
            type="primary",
            use_container_width=True,
        ):

            # Initialize silently.
            backend_ready = initialize_security_engine()

            if backend_ready is None:

                st.error(USER_ERROR_MESSAGE)

            else:

                with st.spinner(
                    "የቴሌብር ሴኩሪቲ ሲስተም "
                    "ምስሉን በመመርመር ላይ ነው..."
                ):

                    model = get_model_safely()

                    if model is None:

                        result = None
                        analysis_error = USER_ERROR_MESSAGE

                    else:

                        result, analysis_error = perform_analysis(
                            model=model,
                            image=image,
                        )

                if analysis_error:

                    st.error(USER_ERROR_MESSAGE)

                elif result:

                    display_result(result)

                else:

                    st.error(USER_ERROR_MESSAGE)


# ============================================================
# DEMO SECTION
# ============================================================

st.divider()

st.markdown("## 🧪 Demo / Sample Analysis")

st.write(
    "ይህ ክፍል ለውድድር ማሳያ በፍጥነት የስርዓቱን "
    "የውጤት
