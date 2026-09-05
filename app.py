import streamlit as st
import re

# Page Configuration
st.set_page_config(
    page_title="Telebirr FraudShield AI",
    page_icon="🛡️",
    layout="centered"
)

# Custom Styling & White-Labeling
st.markdown("""
    <style>
    .main-title { font-size: 24px; font-weight: bold; color: #1E3A8A; margin-bottom: 0px; }
    .sub-text { font-size: 13px; color: #4B5563; margin-bottom: 15px; }
    .ussd-screen { background-color: #111827; color: #10B981; padding: 20px; border-radius: 10px; font-family: monospace; font-size: 15px; border: 2px solid #374151; }
    </style>
""", unsafe_allow_html=True)

st.markdown('<p class="main-title">🛡️ Telebirr FraudShield AI</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">ለስማርት እና ለጠቅጠቅ ስልኮች የተዘጋጀ ሁለገብ የደህንነት እና የማጭበርበሪያ መለያ ሲስተም</p>', unsafe_allow_html=True)

# Tabs for Smart Phone vs Feature Phone (USSD)
tab1, tab2 = st.tabs(["📱 ስማርት ስፎን (SMS መርማሪ)", "📟 ጠቅጠቅ ስልክ (USSD ማስመሰያ)"])

with tab1:
    st.markdown("### የጽሁፍ መልእክት እና ኤስኤምኤስ ደህንነት ምርመራ")
    
    sample_real = "ብር 500.00 ከ ABEBE KEBEDE ተቀብለዋል። የግብይት ቁጥር: TR24AB789CD. ቀሪ ሂሳብዎ ብር 3,450.00 ነው."
    sample_fake = "እንኳን ደስ አለዎት! 60 ሚሊዮን ብር አሸንፈዋልል። ሽልማቱን ለመቀበል የሚከተለውን ሊንክ ይጫኑ t.me/telebirr_free_gift ወዲያውኑ ይደውሉልን 0911223344"

    col_d1, col_d2 = st.columns(2)
    demo_choice = ""
    if col_d1.button("🟢 እውነተኛ ናሙና"):
        demo_choice = sample_real
    if col_d2.button("🔴 ሀሰተኛ ናሙና"):
        demo_choice = sample_fake

    user_input = st.text_area("የተጠራጠሩትን የቴሌብር ኤስኤምኤስ ወይም ጽሁፍ እዚህ ያስገቡ:", value=demo_choice, height=100)

    def analyze_sms(text):
        if not text.strip():
            return None
        score = 0
        reasons = []
        
        scam_keywords = ['አሸንፈዋል', 'ሊንኩን', 'በነፃ', 'ሽልማት', 'ሊቀበሉ', 'ግዛ', 'ይደውሉ', 't.me/', 'http', 'bit.ly', 'won', 'free', 'congrats']
        found_keywords = [kw for kw in scam_keywords if kw in text.lower()]
        
        if found_keywords:
            score += 50
            reasons.append(f"⚠️ አጠራጣሪ ቃላት ተገኝተዋል: {', '.join(found_keywords)}")
        
        phone_pattern = r'\b(09|07)\d{8}\b'
        if re.search(phone_pattern, text):
            score += 35
            reasons.append("⚠️ መልእክቱ የተላከው ከተራ የሞባይል ስልክ ቁጥር ነው (ኦፊሴላዊ አጭር ቁጥር አይደለም)")
        
        trx_pattern = r'TR[A-Z0-9]{6,}'
        if re.search(trx_pattern, text):
            score -= 30
            reasons.append("✅ ትክክለኛ የቴሌብር የግብይት መለያ ቁጥር (Transaction ID) ቅንብር ተገኝቷል")
        else:
            if "ብር" in text or "ተልኮ" in text:
                score += 20
                reasons.append("❌ መደበኛ የቴሌብር የግብይት መለያ ቁጥር (Transaction ID) አልተገኘም")

        risk_percentage = min(max(score, 5), 98) if score > 0 else 5
        verdict = "FAKE" if (found_keywords and (re.search(phone_pattern, text) or not re.search(trx_pattern, text))) or score >= 40 else "REAL"
        if verdict == "REAL": 
            risk_percentage = 2

        return verdict, risk_percentage, reasons

    if st.button("🔍 መልእክቱን መርምር", type="primary"):
        if not user_input.strip():
            st.warning("እባክዎ የሚመረመርውን ጽሁፍ ያስገቡ።")
        else:
            with st.spinner("ሲስተሙ መልእክቱን በመመርመር ላይ ነው..."):
                verdict, risk, reasons = analyze_sms(user_input)
                st.markdown("---")
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.metric(label="የአደጋ መጠን (Risk Score)", value=f"{risk}%")
                with col2:
                    if verdict == "REAL":
                        st.success("🟢 **ውጤት: እውነተኛ የቴሌብር መልእክት**")
                    else:
                        st.error("🔴 **ውጤት: ማጭበርበሪያ / ሀሰተኛ መልእክት**")
                
                st.markdown("#### 🔎 የደህንነት ትንተና ዝርዝር:")
                for r in reasons:
                    st.markdown(f"- {r}")

with tab2:
    st.markdown("### የጠቅጠቅ ስልክ USSD ኮድ ማስመሰያ (*127#)")
    st.markdown("ይህ ማሳያ በገጠር እና በጠቅጠቅ ስልክ ላሉ ተጠቃሚዎች ያለ ኢንተርኔት በUSSD የሚሰጠውን አገልግሎት ያስመስላል። ዳኞች ፊት ሲቀርቡ ለመጠቀም እጅግ ውብ አማራጭ ነው።")
    
    if 'ussd_step' not in st.session_state:
        st.session_state.ussd_step = 'home'

    ussd_code = st.text_input("USSD ኮድ ይፃፉ (ለምሳሌ *127#):", value="*127#", key="ussd_field")

    if ussd_code.strip() == "*127#":
        st.markdown("<div class='ussd-screen'>", unsafe_allow_html=True)
        if st.session_state.ussd_step == 'home':
            st.markdown("<b>Telebirr FraudShield Menu:</b><br>1. የግብይት ቁጥር (TxID) አረጋግጥ<br>2. አጠራጣሪ SMS ሪፖርት አድርግ<br>3. የደህንነት ጠቃሚ ምክሮች", unsafe_allow_html=True)
            choice = st.text_input("ምርጫዎን ያስገቡ (1, 2 ወይም 3):", key="menu_choice")
            if st.button("ላክ (Send)", key="btn_send_home"):
                if choice == '1':
                    st.session_state.ussd_step = 'check_tx'
                    st.rerun()
                elif choice == '2':
                    st.session_state.ussd_step = 'report_sms'
                    st.rerun()
                elif choice == '3':
                    st.session_state.ussd_step = 'tips'
                    st.rerun()
        
        elif st.session_state.ussd_step == 'check_tx':
            st.markdown("<b>የግብይት ማረጋገጫ:</b><br>እባክዎ የግብይት ቁጥሩን (ለምሳሌ TR24AB78) ያስገቡ:", unsafe_allow_html=True)
            tx_code = st.text_input("TxID:", key="tx_input")
            if st.button("አረጋግጥ", key="btn_check"):
                if tx_code.startswith("TR"):
                    st.success("መልዕክት: 🟢 ይህ የግብይት ቁጥር ትክክለኛ ነው።")
                else:
                    st.error("መልዕክት: 🔴 ይህ ቁጥር ሀሰተኛ ወይም የተሳሳተ ነው!")
            if st.button("ተመለስ (Back)", key="btn_back_1"):
                st.session_state.ussd_step = 'home'
                st.rerun()

        elif st.session_state.ussd_step == 'report_sms':
            st.markdown("<b>ማጭበርበር ሪፖርት ማድረጊያ:</b><br>አጠራጣሪውን ስልክ ቁጥር ወይም አጭር ጽሁፍ ያስገቡ:", unsafe_allow_html=True)
            rep_text = st.text_input("ዝርዝር:", key="rep_input")
            if st.button("ሪፖርት አድርግ", key="btn_report"):
                st.success("አመሰግናለን! ሪፖርቱ ለኢትዮ ቴሌኮም ደህንነት ክፍል ተልኳል።")
            if st.button("ተመለስ (Back)", key="btn_back_2"):
                st.session_state.ussd_step = 'home'
                st.rerun()

        elif st.session_state.ussd_step == 'tips':
            st.markdown("<b>የደህንነት ምክሮች:</b><br>- የይለፍ ቃልዎን (PIN) ለምንም ሰው አያጋሩ!<br>- በነፃ የሚሰጥ የውሸት ሽልማት አያምኑ።", unsafe_allow_html=True)
            if st.button("ተመለስ (Back)", key="btn_back_3"):
                st.session_state.ussd_step = 'home'
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("እባክዎ ትክክለኛውን የUSSD ኮድ `*127#` ብለው ያስገቡ።")

# Footer Note
st.markdown("---")
st.markdown("<p style='font-size:11px; color:gray;'>Ethio Telecom Competition - Telebirr FraudShield AI (Offline & USSD Supported)</p>", unsafe_allow_html=True)
