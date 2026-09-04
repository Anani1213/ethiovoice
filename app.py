import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import re
import io

# ----------------------------------------------------------------------
# Page Configuration
# ----------------------------------------------------------------------
st.set_page_config(
    page_title="Telebirr AI FraudShield (Vision Edition)",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------
# System Prompt (exact as specified)
# ----------------------------------------------------------------------
SYSTEM_PROMPT = (
    "You are an expert Telebirr forensic transaction analyzer. "
    "Carefully inspect this receipt screenshot for sign of photoshop editing, "
    "inconsistent fonts, misaligned numbers, altered transaction IDs, "
    "incorrect colors, or AI-generated artifacts. "
    "Provide a response in clear Amharic with: "
    "1) Verdict (🟢 እውነተኛ / 🔴 የትስስር/የተቀየረ/የተሰረዘ ሀሰተኛ ደረሰኝ), "
    "2) Fraud Risk Level (0-100%), and "
    "3) Detailed Amharic Bulleted Reasons explaining your findings "
    "(e.g. ፎንቱ የተለየ ነው፣ የግብይት ቁጥሩ ቅርፅ አይጣጣምም)."
)

# ----------------------------------------------------------------------
# Configure Gemini API
# ----------------------------------------------------------------------
def configure_gemini() -> bool:
    """
    Configure the Gemini API with the key from st.secrets.
    Returns True if successful, False otherwise.
    """
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        return True
    except KeyError:
        st.error("⚠️ GEMINI_API_KEY not found in st.secrets. Please add it to your secrets file.")
        return False
    except Exception as e:
        st.error(f"⚠️ Failed to configure Gemini API: {e}")
        return False

# ----------------------------------------------------------------------
# Helper: Analyze image with Gemini
# ----------------------------------------------------------------------
def analyze_image_with_gemini(image: Image.Image):
    """
    Send the image to Gemini with the forensic system prompt and return the response text.
    Handles API errors gracefully and returns None on failure.
    """
    try:
        # Create the model with system instruction
        model = genai.GenerativeModel('gemini-1.5-flash', system_instruction=SYSTEM_PROMPT)

        # Generate content – pass the PIL Image directly
        response = model.generate_content([image])

        # Extract text from response
        if response and hasattr(response, 'text'):
            return response.text
        else:
            st.warning("No text response received from Gemini.")
            return None
    except Exception as e:
        st.error(f"❌ API Error: {e}")
        return None

# ----------------------------------------------------------------------
# Helper: Extract fraud risk percentage from response text
# ----------------------------------------------------------------------
def extract_risk_percentage(text: str) -> int:
    """
    Attempt to extract the fraud risk percentage from the Gemini response.
    Looks for patterns like 'Risk Level: 75%' or a standalone number followed by %.
    Returns -1 if not found.
    """
    if not text:
        return -1

    # First try to find pattern with % sign
    match = re.search(r'(\d{1,3})\s*%', text)
    if match:
        return int(match.group(1))

    # Try to find after "Risk Level" (case insensitive)
    match = re.search(r'risk\s*level\s*[:：]\s*(\d{1,3})', text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return -1

# ----------------------------------------------------------------------
# Helper: Generate a synthetic Telebirr receipt for demo
# ----------------------------------------------------------------------
def generate_sample_receipt() -> Image.Image:
    """
    Create a synthetic Telebirr receipt screenshot using PIL.
    This is only for demonstration purposes.
    """
    img = Image.new('RGB', (600, 500), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Try to use a common font, fallback to default
    try:
        font_title = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
        font_body = ImageFont.truetype("DejaVuSans.ttf", 16)
    except:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Draw border
    draw.rectangle([20, 20, 580, 480], outline=(200, 200, 200), width=2)

    # Header
    draw.text((50, 40), "Telebirr Transaction Receipt", fill=(0, 0, 0), font=font_title)
    draw.text((50, 80), "----------------------------------", fill=(150, 150, 150), font=font_body)

    # Details
    y = 120
    details = [
        "Transaction ID: TB202406151234567",
        "Amount: 100.00 ETB",
        "Date: 2024-06-15 14:30:00",
        "Sender: Abebe Kebede",
        "Receiver: Almaz Tesfaye",
        "Status: SUCCESS",
    ]
    for line in details:
        draw.text((50, y), line, fill=(0, 0, 0), font=font_body)
        y += 30

    # Fake logo bar
    draw.rectangle([50, 400, 550, 430], fill=(0, 128, 0))
    draw.text((250, 405), "Telebirr", fill=(255, 255, 255), font=font_body)

    return img

# ----------------------------------------------------------------------
# Display analysis results
# ----------------------------------------------------------------------
def display_results(response_text: str):
    """Parse and display the Gemini response in a structured UI."""
    if not response_text:
        st.error("No analysis results available.")
        return

    st.markdown("## 🔍 Analysis Results")

    # Extract risk percentage
    risk_percent = extract_risk_percentage(response_text)
    col1, col2 = st.columns([1, 1])

    with col1:
        if risk_percent >= 0:
            st.metric("Fraud Risk Level", f"{risk_percent}%")
        else:
            st.metric("Fraud Risk Level", "N/A")

    with col2:
        if "🟢" in response_text:
            st.success("Verdict: 🟢 እውነተኛ (Genuine)")
        elif "🔴" in response_text:
            st.error("Verdict: 🔴 ሀሰተኛ ደረሰኝ (Fraudulent)")
        else:
            st.warning("Verdict could not be determined from response.")

    # Display full response in markdown
    st.markdown("### Detailed Findings (Amharic)")
    st.markdown(response_text)

# ----------------------------------------------------------------------
# Main Application
# ----------------------------------------------------------------------
def main():
    st.title("🛡️ Telebirr AI FraudShield (Vision Edition)")
    st.markdown(
        """
        Upload a screenshot of a Telebirr transaction receipt or SMS.
        Our AI will analyze it for signs of tampering, forgery, or AI‑generated fraud.
        """
    )

    # Configure Gemini API
    if not configure_gemini():
        st.stop()

    # Create tabs
    tab1, tab2 = st.tabs(["📤 Upload Receipt", "🎯 Demo / Sample Analysis"])

    # ------------------ TAB 1: Upload Receipt ------------------
    with tab1:
        st.subheader("Upload a Receipt Screenshot")
        uploaded_file = st.file_uploader(
            "Choose an image (PNG, JPG, JPEG)",
            type=["png", "jpg", "jpeg"],
            help="Upload a clear screenshot of the Telebirr receipt.",
        )

        if uploaded_file is not None:
            # Read and display image
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Receipt", use_column_width=True)

            if st.button("🔍 Analyze This Receipt", type="primary"):
                with st.spinner("Analyzing receipt with AI..."):
                    response_text = analyze_image_with_gemini(image)
                    if response_text:
                        display_results(response_text)

    # ------------------ TAB 2: Demo / Sample Analysis ------------------
    with tab2:
        st.subheader("Try a Sample Analysis")
        st.markdown(
            """
            No receipt? No problem! Generate a synthetic Telebirr receipt and see how the AI
            performs its forensic analysis.
            """
        )

        if st.button("🎯 Run Sample Analysis", type="primary"):
            # Generate a sample receipt
            sample_image = generate_sample_receipt()
            st.image(sample_image, caption="Synthetic Sample Receipt", use_column_width=True)

            with st.spinner("Analyzing sample receipt with AI..."):
                response_text = analyze_image_with_gemini(sample_image)
                if response_text:
                    display_results(response_text)

if __name__ == "__main__":
    main()
