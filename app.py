# app.py
# Telebirr AI FraudShield (Vision Edition)
#
# Run:
#   pip install streamlit pillow google-generativeai
#   streamlit run app.py
#
# .streamlit/secrets.toml:
#   GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"

import re
import streamlit as st
from PIL import Image
import google.generativeai as genai


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Telebirr AI FraudShield",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>
        .main {
            padding-top: 1rem;
        }

        .hero {
            padding: 1.5rem 1.8rem;
            border-radius: 18px;
            background: linear-gradient(135deg, #0b6b4f, #064e3b);
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 8px 30px rgba(0,0,0,0.12);
        }

        .hero h1 {
            margin: 0;
            font-size: 2.25rem;
        }

        .hero p {
            margin: 0.5rem 0 0 0;
            font-size: 1.05rem;
            opacity: 0.92;
        }

        .card {
            padding: 1.2rem;
            border-radius: 15px;
            border: 1px solid rgba(128,128,128,0.25);
            margin-bottom: 1rem;
        }

        .risk-low {
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid #16a34a;
            background: rgba(22,163,74,0.08);
        }

        .risk-medium {
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid #ca8a04;
            background: rgba(202,138,4,0.08);
        }

        .risk-high {
            padding: 1rem;
            border-radius: 12px;
            border: 1px solid #dc2626;
            background: rgba(220,38,38,0.08);
        }

        .footer {
            text-align: center;
            padding: 2rem 0 1rem 0;
            opacity: 0.65;
            font-size: 0.85rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

def configure_gemini():
    """Safely configure Gemini using Streamlit secrets."""
    try:
        api_key = st.secrets.get("GEMINI_API_KEY")

        if not api_key:
            return None, (
                "GEMINI_API_KEY አልተገኘም። "
                "በ .streamlit/secrets.toml ውስጥ API key ያስገቡ።"
            )

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-1.5-flash")
        return model, None

    except Exception as exc:
        return None, f"Gemini ማዋቀር አልተቻለም፦ {exc}"


# ============================================================
# FORENSIC SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are an expert Telebirr forensic transaction analyzer.

Carefully inspect this uploaded Telebirr transaction receipt or SMS screenshot.

Your job is to identify visual signs that the screenshot may have been:
- Photoshopped or manually edited
- AI-generated
- Digitally altered
- Cropped or manipulated to hide information
- Modified to change transaction IDs
- Modified to change amounts
- Modified to change dates/times
- Modified to change sender/receiver information

Inspect carefully for:
- inconsistent fonts
- inconsistent font sizes
- unusual letter spacing
- misaligned numbers
- altered transaction IDs
- suspicious digit shapes
- incorrect colors
- inconsistent spacing
- inconsistent shadows
- compression artifacts around edited areas
- duplicated pixels or suspicious edges
- inconsistent background patterns
- AI-generated visual artifacts
- suspicious alignment
- suspicious formatting
- unusual UI elements
- inconsistent dates or times
- inconsistent currency/amount formatting

IMPORTANT:
A screenshot alone cannot prove that a transaction actually occurred.
Do not claim that the transaction is verified against Telebirr's servers.
Your result is a visual forensic assessment only.

Return the result in clear Amharic.

Use exactly this structure:

VERDICT: [🟢 እውነተኛ / 🔴 የተቀየረ/የተሰረዘ ሀሰተኛ ደረሰኝ]

RISK: [0-100]%

REASONS:
- [Detailed reason]
- [Detailed reason]
- [Detailed reason]

CONFIDENCE: [0-100]%

LIMITATIONS:
- [Brief limitation of visual-only analysis]

If the evidence is inconclusive, do NOT automatically call it fake.
Use the verdict that best matches the visual evidence and explain uncertainty.
"""


# ============================================================
# IMAGE ANALYSIS
# ============================================================

def analyze_image(model, image):
    """
    Send PIL image directly to Gemini Vision.
    Returns text or a friendly error message.
    """
    try:
        response = model.generate_content(
            [
                SYSTEM_PROMPT,
                image,
            ],
            generation_config={
                "temperature": 0.1,
                "max_output_tokens": 1200,
            },
        )

        if response is None:
            return None, "Gemini ምንም ምላሽ አልሰጠም።"

        text = getattr(response, "text", None)

        if not text:
            return None, (
                "Gemini ምላሹ ባዶ ነው። "
                "ምስሉ ግልጽ መሆኑን ያረጋግጡ።"
            )

        return text.strip(), None

    except Exception as exc:
        error_text = str(exc)

        # Make common API failures more understandable.
        if "404" in error_text:
            message = (
                "Gemini model/API endpoint አልተገኘም። "
                "API key እና Gemini SDK configuration ያረጋግጡ።"
            )
        elif "403" in error_text or "permission" in error_text.lower():
            message = (
                "Gemini API ፍቃድ ችግር አለ። "
                "API key እና API access ያረጋግጡ።"
            )
        elif "429" in error_text:
            message = (
                "Gemini API rate limit ደርሷል። "
                "እባክዎ ትንሽ ጊዜ ይጠብቁና እንደገና ይሞክሩ።"
            )
        else:
            message = f"ምስሉን መተንተን አልተቻለም፦ {error_text}"

        return None, message


# ============================================================
# RESULT PARSING
# ============================================================

def extract_risk(text):
    """Extract risk percentage from Gemini response."""
    if not text:
        return None

    patterns = [
        r"RISK\s*:\s*\[?\s*(\d{1,3})\s*%?",
        r"Risk\s*:\s*\[?\s*(\d{1,3})\s*%?",
        r"(\d{1,3})\s*%",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                value = int(match.group(1))
                return max(0, min(100, value))
            except ValueError:
                pass

    return None


def extract_verdict(text):
    """Extract verdict from Gemini response."""
    if not text:
        return None

    if "🔴" in text:
        return "🔴 የተቀየረ/የተሰረዘ ሀሰተኛ ደረሰኝ"

    if "🟢" in text:
        return "🟢 እውነተኛ"

    if "ሀሰተኛ" in text or "ተቀየረ" in text:
        return "🔴 ሊሆን የሚችል ሀሰተኛ/የተቀየረ"

    return "⚪ ውጤቱ ግልጽ አይደለም"


def display_analysis(result_text):
    """Render Gemini's forensic result in a clean dashboard."""

    verdict = extract_verdict(result_text)
    risk = extract_risk(result_text)

    st.markdown("## 🔎 የAI የForensic ትንተና")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Verdict")
        if verdict and "🔴" in verdict:
            st.error(verdict)
        elif verdict and "🟢" in verdict:
            st.success(verdict)
        else:
            st.warning(verdict or "ያልታወቀ")

    with col2:
        st.markdown("### Fraud Risk")
        if risk is not None:
            st.metric(
                label="የማጭበርበር አደጋ",
                value=f"{risk}%",
            )

            if risk >= 70:
                st.error("ከፍተኛ አደጋ")
            elif risk >= 40:
                st.warning("መካከለኛ አደጋ")
            else:
                st.success("ዝቅተኛ አደጋ")
        else:
            st.metric(
                label="የማጭበርበር አደጋ",
                value="N/A",
            )

    with col3:
        st.markdown("### Analysis Status")
        st.success("Gemini Vision ትንተና ተጠናቋል")

    st.divider()

    st.markdown("### 📋 ዝርዝር የAI ሪፖርት")

    # Remove the duplicated headline fields from the main body
    # so the report is easier to read.
    cleaned_result = re.sub(
        r"VERDICT\s*:\s*\[?.*?\]?\s*",
        "",
        result_text,
        flags=re.IGNORECASE,
    )

    cleaned_result = re.sub(
        r"RISK\s*:\s*\[?.*?\]?\s*",
        "",
        cleaned_result,
        flags=re.IGNORECASE,
    )

    st.markdown(cleaned_result.strip())

    st.info(
        "⚠️ ማስታወሻ፦ ይህ ውጤት በምስሉ ላይ ብቻ የተመሰረተ "
        "forensic assessment ነው። ትክክለኛ የTelebirr ግብይት "
        "መኖሩን በserver/database ላይ አያረጋግጥም።"
    )


# ============================================================
# DEMO ANALYSIS
# ============================================================

DEMO_RESULT = """
VERDICT: 🟢 እውነተኛ

RISK: 12%

REASONS:
- የደረሰኙ የጽሁፍ ፎንትና መጠን በአብዛኛው ተመሳሳይ ነው።
- የTransaction ID ቁጥሮች አቀማመጥ ከሌሎች የጽሁፍ ክፍሎች ጋር ይጣጣማል።
- በAmount እና Transaction ID አካባቢ ግልጽ የPhotoshop ምልክት አልታየም።
- የbackground እና የጽሁፍ ጥራት በአብዛኛው ወጥ ነው።
- ግልጽ የAI-generated artifact አልተገኘም።

CONFIDENCE: 82%

LIMITATIONS:
- ይህ የvisual-only analysis ስለሆነ ግብይቱን ከTelebirr server ጋር በቀጥታ አያረጋግጥም።
"""


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:
    st.header("🛡️ FraudShield")

    st.markdown(
        """
        **Telebirr AI FraudShield**

        የTelebirr receipt/SMS screenshot
        በGemini Vision AI በመጠቀም
        የvisual fraud ምልክቶችን ይመረምራል።
        """
    )

    st.divider()

    st.markdown("### 🔍 ምን ይመረምራል?")
    st.markdown(
        """
        - 🖼️ Photoshop edits
        - 🤖 AI-generated artifacts
        - 🔢 Transaction ID changes
        - 💰 Amount manipulation
        - 🔤 Font inconsistencies
        - 📐 Alignment problems
        - 🎨 Color inconsistencies
        """
    )

    st.divider()

    st.caption(
        "Competition Prototype • Vision Edition"
    )


# ============================================================
# HERO
# ============================================================

st.markdown(
    """
    <div class="hero">
        <h1>🛡️ Telebirr AI FraudShield</h1>
        <p>
            Vision Edition — AI-powered forensic screening for
            suspicious Telebirr receipts and transaction screenshots.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# INTRODUCTION
# ============================================================

intro_col1, intro_col2 = st.columns([2, 1])

with intro_col1:
    st.markdown("## 🔎 ደረሰኝዎን ይመርምሩ")
    st.write(
        "የTelebirr transaction receipt ወይም SMS screenshot "
        "ያስገቡ። Gemini Vision AI ምስሉን በመመርመር "
        "የተቀየረ ወይም አጠራጣሪ የሆነ የvisual evidence "
        "ለመፈለግ ይሞክራል።"
    )

with intro_col2:
    st.metric(
        label="Supported Formats",
        value="PNG / JPG / JPEG",
    )


# ============================================================
# GEMINI INITIALIZATION
# ============================================================

model, config_error = configure_gemini()

if config_error:
    st.warning(
        f"⚠️ Gemini configuration: {config_error}"
    )


# ============================================================
# FILE UPLOADER
# ============================================================

uploaded_file = st.file_uploader(
    "📤 Telebirr Receipt / SMS Screenshot ያስገቡ",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=False,
    help="PNG, JPG ወይም JPEG image ያስገቡ።",
)


# ============================================================
# UPLOADED IMAGE
# ============================================================

if uploaded_file is not None:

    try:
        image = Image.open(uploaded_file)

        # Ensure a compatible RGB/RGBA image is passed to Gemini.
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")

        st.divider()

        image_col, info_col = st.columns([1.2, 1])

        with image_col:
            st.markdown("### 🖼️ Uploaded Screenshot")

            st.image(
                image,
                caption=uploaded_file.name,
                use_container_width=True,
            )

        with info_col:
            st.markdown("### 📄 Image Information")

            width, height = image.size

            st.metric("Width", f"{width}px")
            st.metric("Height", f"{height}px")
            st.metric("Format", uploaded_file.type or "Image")

            st.info(
                "ምስሉ ለGemini Vision ለvisual forensic analysis "
                "ብቻ ይላካል።"
            )

        st.divider()

        analyze_col1, analyze_col2 = st.columns([1, 2])

        with analyze_col1:
            analyze_button = st.button(
                "🔍 Analyze with Gemini Vision",
                type="primary",
                use_container_width=True,
            )

        with analyze_col2:
            st.caption(
                "AI የምስሉን fonts, alignment, IDs, amounts, "
                "colors እና possible manipulation artifacts ይመረምራል።"
            )

        if analyze_button:

            if model is None:
                st.error(
                    "Gemini API አልተዘጋጀም። "
                    "GEMINI_API_KEY በStreamlit secrets ውስጥ ያስገቡ።"
                )

            else:
                with st.spinner(
                    "🔬 Gemini Vision ምስሉን በforensic መንገድ እየመረመረ ነው..."
                ):
                    result, error = analyze_image(
                        model,
                        image,
                    )

                if error:
                    st.error(error)
                elif result:
                    display_analysis(result)


    except Exception as exc:
        st.error(
            f"❌ ምስሉን መክፈት አልተቻለም፦ {exc}"
        )


# ============================================================
# DEMO / SAMPLE ANALYSIS
# ============================================================

st.divider()

st.markdown("## 🧪 Demo / Sample Analysis")
st.write(
    "ለዳኞች ፈጣን demo፦ ፎቶ ሳያስገቡ የsample forensic "
    "analysis ውጤትን ማየት ይችላሉ።"
)

demo_col1, demo_col2 = st.columns([1, 2])

with demo_col1:
    demo_button = st.button(
        "🚀 Run Demo Analysis",
        type="secondary",
        use_container_width=True,
    )

with demo_col2:
    st.caption(
        "Demo ውጤቱ ለUI/competition presentation ነው፤ "
        "የእውነተኛ ግብይት ማረጋገጫ አይደለም።"
    )

if demo_button:
    display_analysis(DEMO_RESULT)


# ============================================================
# HOW IT WORKS
# ============================================================

st.divider()

st.markdown("## ⚙️ How It Works")

step1, step2, step3 = st.columns(3)

with step1:
    st.markdown(
        """
        ### 1️⃣ Upload
        Telebirr receipt ወይም SMS screenshot
        ያስገቡ።
        """
    )

with step2:
    st.markdown(
        """
        ### 2️⃣ Vision AI
        Gemini Vision የምስሉን fonts,
        numbers, IDs, colors እና alignment
        ይመረምራል።
        """
    )

with step3:
    st.markdown(
        """
        ### 3️⃣ Risk Report
        Verdict, Fraud Risk % እና
        ዝርዝር የAmharic forensic reasons
        ይሰጣል።
        """
    )


# ============================================================
# SAFETY / LIMITATION
# ============================================================

st.divider()

st.warning(
    """
    ⚠️ **Important:** Telebirr AI FraudShield is a visual
    forensic screening prototype. AI cannot establish with
    certainty that a financial transaction occurred from a
    screenshot alone. For real financial verification,
    transaction details should be checked through an
    authorized Telebirr system/API or official records.
    """
)


# ============================================================
# FOOTER
# ============================================================

st.markdown(
    """
    <div class="footer">
        🛡️ Telebirr AI FraudShield — Vision Edition<br>
        AI-powered visual fraud screening • Competition Prototype
    </div>
    """,
    unsafe_allow_html=True,
            )
