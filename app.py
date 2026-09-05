"""
Telebirr FraudShield — Offline & USSD Hybrid Edition
-----------------------------------------------------
A fully local, rule-based SMS/transaction forensic inspector and USSD
simulator built for the Ethio Telecom Innovation Challenge.

No external AI services, no API keys, no network calls of any kind.
Every decision is made with plain Python string/regex heuristics.
"""

import html
import re

import streamlit as st

# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Telebirr FraudShield",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# GLOBAL STYLING
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .main-header {
            background: linear-gradient(90deg, #0a5c36 0%, #128a4a 100%);
            padding: 1.4rem 1.8rem;
            border-radius: 14px;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 14px rgba(0,0,0,0.15);
        }
        .main-header h1 {
            color: #ffffff;
            margin: 0;
            font-size: 1.9rem;
        }
        .main-header p {
            color: #e6f4ea;
            margin: 0.35rem 0 0 0;
            font-size: 0.95rem;
        }

        .verdict-safe {
            background-color: #e6f6ea;
            border-left: 8px solid #1e8e3e;
            color: #145a24;
            padding: 1rem 1.2rem;
            border-radius: 10px;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }
        .verdict-fraud {
            background-color: #fce8e6;
            border-left: 8px solid #c5221f;
            color: #7a1210;
            padding: 1rem 1.2rem;
            border-radius: 10px;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
        }

        .ussd-phone {
            background: #161616;
            border-radius: 26px;
            padding: 22px;
            max-width: 380px;
            margin: 0.5rem auto 1.2rem auto;
            box-shadow: 0 0 0 6px #2b2b2b, 0 10px 30px rgba(0,0,0,0.4);
        }
        .ussd-header {
            text-align: center;
            color: #9aa39a;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
            margin-bottom: 10px;
            font-family: 'Courier New', monospace;
        }
        .ussd-screen {
            background: #0a1f0f;
            color: #3cff5e;
            font-family: 'Courier New', monospace;
            font-size: 1rem;
            line-height: 1.55;
            padding: 18px;
            border-radius: 6px;
            min-height: 260px;
            white-space: pre-wrap;
            border: 1px solid #1f4d2a;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# LOCAL FORENSIC RULE ENGINE (no external services — pure Python heuristics)
# ---------------------------------------------------------------------------
RED_FLAG_CATEGORIES = [
    {
        "name": "የማባበያ/ሽልማት ቃላት",
        "keywords": [
            "አሸንፈዋል", "ሽልማት", "በነፃ", "ነፃ ስጦታ", "እድለኛ ተጠቃሚ",
            "ኮድ ገብተው ያሸንፉ", "bonus", "winner", "free gift", "lottery",
        ],
        "weight": 25,
    },
    {
        "name": "የአስቸኳይ ጊዜ ማስፈራሪያ",
        "keywords": [
            "አሁኑኑ", "ወዲያውኑ", "በአስቸኳይ", "ይታገዳል", "ይዘጋል",
            "የመጨረሻ ማስጠንቀቂያ", "expire", "24 ሰዓት", "ካልሆነ",
        ],
        "weight": 15,
    },
    {
        "name": "የፒን/የይለፍ ቃል ጥያቄ",
        "keywords": ["ፒን", "ፒንዎን", "የይለፍ ቃል", "password", "pin code", "otp"],
        "weight": 35,
    },
    {
        "name": "አጠራጣሪ ሊንክ",
        "keywords": [
            "t.me/", "bit.ly", "tinyurl", "wa.me/", "http://", "https://",
            "ሊንኩን", "ሊንክ ይጫኑ", ".xyz", ".click",
        ],
        "weight": 25,
    },
]

PERSONAL_NUMBER_PATTERN = re.compile(r"\b(09|07)\d{8}\b")
OFFICIAL_SHORTCODES = ["127", "9014", "8000", "9800"]
TX_ID_PATTERN = re.compile(r"\bTR[0-9A-Z]{6,14}\b", re.IGNORECASE)
TRANSACTION_CONTEXT_WORDS = [
    "ግብይት", "ብር ደርሶዎታል", "ደርሶታል", "ተልኳል", "ቀሪ ሂሳብ",
    "balance", "transaction", "ተቀብለዋል",
]

SAMPLE_REAL = (
    "የ1,500.00 ብር ክፍያ ለ Global Insurance PLC በተሳካ ሁኔታ ተልኳል። "
    "የግብይት መለያ ቁጥር: TR251A8B9C21። አዲሱ ቀሪ ሂሳብዎ: 3,240.50 ብር። "
    "እናመሰግናለን - telebirr (127)"
)

SAMPLE_FAKE = (
    "እንኳን ደስ አለዎት! በዛሬው እጣ 50,000 ብር አሸንፈዋል! ሽልማትዎን አሁኑኑ ለመቀበል "
    "የፒን ቁጥርዎን በዚህ ሊንክ ያስገቡ፡ t.me/telebirr_bonus2026 "
    "ይህ እድል በ24 ሰዓት ውስጥ ያበቃል! ለበለጠ መረጃ በ0912345678 ይደውሉ።"
)


def analyze_sms(text: str):
    """Run the local rule-based forensic engine over a message.

    Returns a dict with a 0-100 risk score, a verdict, and a list of
    human-readable findings — or None if there is nothing to analyze.
    """
    if not text or not text.strip():
        return None

    risk = 0
    findings = []
    lowered = text.lower()

    # 1. Keyword category scan
    for category in RED_FLAG_CATEGORIES:
        hits = [kw for kw in category["keywords"] if kw.lower() in lowered]
        if hits:
            risk += category["weight"]
            sample_hits = ", ".join(hits[:3])
            findings.append({
                "type": "negative",
                "text": f"{category['name']} ተገኝቷል፦ \u201c{sample_hits}\u201d",
            })

    # 2. Personal phone number instead of an official shortcode
    if PERSONAL_NUMBER_PATTERN.search(text):
        risk += 15
        findings.append({
            "type": "negative",
            "text": "መልእክቱ ወደ ግል ስልክ ቁጥር (09/07) ጥሪ እንዲደረግ ይጠይቃል",
        })

    if any(code in text for code in OFFICIAL_SHORTCODES):
        risk = max(risk - 10, 0)
        findings.append({
            "type": "positive",
            "text": "ኦፊሴላዊ የ telebirr አጭር ኮድ ማጣቀሻ ተገኝቷል",
        })

    # 3. Transaction ID pattern validation
    claims_transaction = any(word.lower() in lowered for word in TRANSACTION_CONTEXT_WORDS)
    tx_match = TX_ID_PATTERN.search(text)
    if claims_transaction:
        if tx_match:
            findings.append({
                "type": "positive",
                "text": f"ትክክለኛ ቅርጸት ያለው የግብይት መለያ ተገኝቷል ({tx_match.group().upper()})",
            })
        else:
            risk += 15
            findings.append({
                "type": "negative",
                "text": "የግብይት ጥያቄ ቢመስልም ትክክለኛ ቅርጸት ያለው Transaction ID አልተገኘም",
            })

    risk = min(max(risk, 0), 100)

    if not findings:
        findings.append({
            "type": "positive",
            "text": "ምንም የታወቀ የማጭበርበሪያ ምልክት አልተገኘም",
        })

    verdict = "ማጭበርበሪያ" if risk >= 50 else "እውነተኛ"
    return {"risk": risk, "verdict": verdict, "findings": findings}


# ---------------------------------------------------------------------------
# SESSION STATE INITIALIZATION (robust across reruns)
# ---------------------------------------------------------------------------
if "sms_text" not in st.session_state:
    st.session_state.sms_text = ""
if "last_result" not in st.session_state:
    st.session_state.last_result = None
if "ussd_screen" not in st.session_state:
    st.session_state.ussd_screen = "home"


def set_sample(sample_text: str):
    st.session_state.sms_text = sample_text
    st.session_state.last_result = None


def run_analysis():
    st.session_state.last_result = analyze_sms(st.session_state.sms_text)


def goto(screen: str):
    st.session_state.ussd_screen = screen


def render_ussd_screen(content: str):
    st.markdown(
        f"""
        <div class="ussd-phone">
            <div class="ussd-header">📶 Ethio Telecom &nbsp;|&nbsp; 🔋 100%</div>
            <div class="ussd-screen">{content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="main-header">
        <h1>🛡️ Telebirr FraudShield</h1>
        <p>የተንቀሳቃሽ ገንዘብ ልውውጥ ደህንነት ስርዓት — Offline &amp; USSD Hybrid Edition</p>
    </div>
    """,
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs([
    "📱 ስማርት ስልክ — SMS መርማሪ",
    "📟 ጠቅጠቅ ስልክ — USSD ማስመሰያ",
])

# ---------------------------------------------------------------------------
# TAB 1 — SMARTPHONE SMS FORENSIC INSPECTOR
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("የ SMS / ግብይት ጽሑፍ መርማሪ")
    st.caption("አጠራጣሪ የ telebirr መልእክት ወይም ግብይት ማሳወቂያ ከታች ይለጥፉ እና ይመርምሩ።")

    demo_col1, demo_col2 = st.columns(2)
    with demo_col1:
        st.button(
            "🟢 እውነተኛ ናሙና",
            use_container_width=True,
            on_click=set_sample,
            args=(SAMPLE_REAL,),
        )
    with demo_col2:
        st.button(
            "🔴 ሀሰተኛ ናሙና",
            use_container_width=True,
            on_click=set_sample,
            args=(SAMPLE_FAKE,),
        )

    st.text_area(
        "የ SMS ጽሑፍ",
        key="sms_text",
        height=150,
        placeholder="የ SMS ወይም የግብይት መልእክት እዚህ ይለጥፉ...",
    )

    st.button("🔍 ተንትን (Analyze)", type="primary", on_click=run_analysis)

    result = st.session_state.last_result
    if result is not None:
        st.markdown("---")
        metric_col, verdict_col = st.columns([1, 2])
        with metric_col:
            st.metric("የአደጋ መጠን (Risk Score)", f"{result['risk']}%")
        with verdict_col:
            if result["verdict"] == "እውነተኛ":
                st.markdown(
                    '<div class="verdict-safe">🟢 እውነተኛ መልእክት ሳይሆን አይቀርም</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div class="verdict-fraud">🔴 ሀሰተኛ / ማጭበርበሪያ መልእክት ነው</div>',
                    unsafe_allow_html=True,
                )

        st.markdown("#### 📋 ዝርዝር ትንተና")
        for finding in result["findings"]:
            icon = "✅" if finding["type"] == "positive" else "⚠️"
            st.markdown(f"- {icon} {finding['text']}")

# ---------------------------------------------------------------------------
# TAB 2 — FEATURE PHONE USSD SIMULATOR (*127#)
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("የ USSD አገልግሎት ማስመሰያ")
    st.caption(
        "የበይነመረብ ግንኙነት ለሌላቸው የ feature phone ተጠቃሚዎች የተዘጋጀ ብሔራዊ አካታችነት ማሳያ።"
    )

    screen = st.session_state.ussd_screen
    divider = "─" * 22

    if screen == "home":
        content = (
            f"*127#\n{divider}\nTelebirr FraudShield\n{divider}\n"
            "1. የግብይት ማረጋገጫ\n"
            "2. አጠራጣሪ መልእክት ሪፖርት\n"
            "3. የደህንነት ምክሮች\n"
            "0. ውጣ\n"
            f"{divider}\nምላሽዎን ይላኩ..."
        )
    elif screen == "check_tx":
        content = (
            f"*127*1#\n{divider}\nየግብይት ማረጋገጫ\n{divider}\n"
            "የግብይት መለያ ቁጥርዎን\n(Transaction ID) ያስገቡ:\n"
            f"{divider}"
        )
    elif screen == "check_tx_result":
        raw_tx = st.session_state.get("ussd_tx_input_value", "") or ""
        tx_clean = raw_tx.strip().upper()
        is_valid = bool(TX_ID_PATTERN.fullmatch(tx_clean)) if tx_clean else False
        safe_tx = html.escape(tx_clean) if tx_clean else "—"
        if is_valid:
            content = (
                f"*127*1#\n{divider}\n✔ ውጤት\n{divider}\n"
                f"መለያ: {safe_tx}\nትክክለኛ ቅርጸት አለው።\n\n"
                "ሙሉ ማረጋገጫ ለማግኘት\n127 ይደውሉ።\n"
                f"{divider}"
            )
        else:
            content = (
                f"*127*1#\n{divider}\n✘ ውጤት\n{divider}\n"
                f"መለያ: {safe_tx}\nትክክለኛ የ telebirr\nቅርጸት የለውም። ይጠንቀቁ!\n"
                f"{divider}"
            )
    elif screen == "report_sms":
        content = (
            f"*127*2#\n{divider}\nአጠራጣሪ መልእክት ሪፖርት\n{divider}\n"
            "የመልእክቱን ይዘት ከታች\nያስገቡና ይላኩ\n"
            f"{divider}"
        )
    elif screen == "report_done":
        content = (
            f"*127*2#\n{divider}\n✔ ሪፖርትዎ ደርሶናል\n{divider}\n"
            "እናመሰግናለን! የ telebirr\nደህንነት ቡድን ጉዳዩን\nይመረምራል።\n"
            f"{divider}"
        )
    elif screen == "tips":
        content = (
            f"*127*3#\n{divider}\nየደህንነት ምክሮች\n{divider}\n"
            "• ፒንዎን ለማንም አይንገሩ\n"
            "• ያልታወቀ ሊንክ አይንኩ\n"
            "• ሽልማት የሚል መልእክት\n  ሲመጣ ይጠንቀቁ\n"
            "• ግብይት ሁሌም በ127\n  ያረጋግጡ\n"
            f"{divider}"
        )
    elif screen == "exit":
        content = (
            f"*127#\n{divider}\nክፍለ ጊዜው ተጠናቋል\n{divider}\n"
            "telebirr FraudShield\nን ስለተጠቀሙ\nእናመሰግናለን።\n"
            f"{divider}"
        )
    else:
        screen = "home"
        content = (
            f"*127#\n{divider}\nTelebirr FraudShield\n{divider}\n"
            "1. የግብይት ማረጋገጫ\n2. አጠራጣሪ መልእክት ሪፖርት\n3. የደህንነት ምክሮች\n0. ውጣ\n"
            f"{divider}\nምላሽዎን ይላኩ..."
        )

    render_ussd_screen(content)

    if screen == "home":
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.button("1️⃣ ግብይት", use_container_width=True, on_click=goto, args=("check_tx",))
        with c2:
            st.button("2️⃣ ሪፖርት", use_container_width=True, on_click=goto, args=("report_sms",))
        with c3:
            st.button("3️⃣ ምክሮች", use_container_width=True, on_click=goto, args=("tips",))
        with c4:
            st.button("0️⃣ ውጣ", use_container_width=True, on_click=goto, args=("exit",))

    elif screen == "check_tx":
        st.text_input(
            "Transaction ID",
            key="ussd_tx_input_value",
            placeholder="ለምሳሌ TR251A8B9C21",
            label_visibility="collapsed",
        )
        c1, c2 = st.columns(2)
        with c1:
            st.button("✅ ላክ", use_container_width=True, on_click=goto, args=("check_tx_result",))
        with c2:
            st.button("🔙 ተመለስ", use_container_width=True, on_click=goto, args=("home",))

    elif screen == "check_tx_result":
        st.button("🔙 ወደ ዋና ማውጫ ተመለስ", use_container_width=True, on_click=goto, args=("home",))

    elif screen == "report_sms":
        st.text_area(
            "የመልእክት ይዘት",
            key="ussd_report_text",
            height=100,
            label_visibility="collapsed",
            placeholder="አጠራጣሪ መልእክቱን እዚህ ይለጥፉ...",
        )
        c1, c2 = st.columns(2)
        with c1:
            st.button("✅ ላክ", use_container_width=True, on_click=goto, args=("report_done",))
        with c2:
            st.button("🔙 ተመለስ", use_container_width=True, on_click=goto, args=("home",))

    elif screen == "report_done":
        st.button("🔙 ወደ ዋና ማውጫ ተመለስ", use_container_width=True, on_click=goto, args=("home",))

    elif screen == "tips":
        st.button("🔙 ወደ ዋና ማውጫ ተመለስ", use_container_width=True, on_click=goto, args=("home",))

    elif screen == "exit":
        st.button("🔄 እንደገና ጀምር (*127#)", use_container_width=True, on_click=goto, args=("home",))

# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------
st.markdown("---")
st.caption(
    "🔒 ይህ መተግበሪያ ለ Ethio Telecom Innovation Challenge የቀረበ ማሳያ ስሪት ነው። "
    "ትንተናው ሙሉ በሙሉ በአካባቢያዊ (local) rule-based logic ላይ የተመሰረተ ነው።"
)
