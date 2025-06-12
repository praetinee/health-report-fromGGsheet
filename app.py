import numpy as np
import streamlit as st
import pandas as pd
import gspread
import json
import html
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="ระบบรายงานสุขภาพ", layout="wide")

# ==================== STYLE ====================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch&display=swap');
    html, body, [class*="css"] {
        font-family: 'Chakra Petch', sans-serif !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==================== LOAD SHEET ====================
@st.cache_data(ttl=300)
def load_google_sheet():
    try:
        service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
        client = gspread.authorize(creds)

        sheet_url = "https://docs.google.com/spreadsheets/d/1N3l0o_Y6QYbGKx22323mNLPym77N0jkJfyxXFM2BDmc"
        worksheet = client.open_by_url(sheet_url).sheet1
        raw_data = worksheet.get_all_records()
        if not raw_data:
            st.error("❌ ไม่พบข้อมูลในแผ่นแรกของ Google Sheet")
            st.stop()
        return pd.DataFrame(raw_data)
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการโหลด Google Sheet: {e}")
        st.stop()

df = load_google_sheet()
df.columns = df.columns.str.strip()
df['เลขบัตรประชาชน'] = df['เลขบัตรประชาชน'].astype(str).str.strip()
df['HN'] = df['HN'].astype(str).str.strip()
df['ชื่อ-สกุล'] = df['ชื่อ-สกุล'].astype(str).str.strip()

# ==================== YEAR MAPPING ====================
years = list(range(61, 69))
columns_by_year = {
    y: {
        "weight": f"น้ำหนัก{y}" if y != 68 else "น้ำหนัก",
        "height": f"ส่วนสูง{y}" if y != 68 else "ส่วนสูง",
        "waist": f"รอบเอว{y}" if y != 68 else "รอบเอว",
        "sbp": f"SBP{y}" if y != 68 else "SBP",
        "dbp": f"DBP{y}" if y != 68 else "DBP",
        "pulse": f"pulse{y}" if y != 68 else "pulse",
    }
    for y in years
}

# ==================== INTERPRET FUNCTIONS ====================
def interpret_bmi(bmi):
    try:
        bmi = float(bmi)
        if bmi > 30:
            return "อ้วนมาก"
        elif bmi >= 25:
            return "อ้วน"
        elif bmi >= 23:
            return "น้ำหนักเกิน"
        elif bmi >= 18.5:
            return "ปกติ"
        else:
            return "ผอม"
    except (ValueError, TypeError):
        return "-"

def interpret_bp(sbp, dbp):
    try:
        sbp = float(sbp)
        dbp = float(dbp)
        if sbp == 0 or dbp == 0:
            return "-"
        if sbp >= 160 or dbp >= 100:
            return "ความดันสูง"
        elif sbp >= 140 or dbp >= 90:
            return "ความดันสูงเล็กน้อย"
        elif sbp < 120 and dbp < 80:
            return "ความดันปกติ"
        else:
            return "ความดันค่อนข้างสูง"
    except (ValueError, TypeError):
        return "-"

def combined_health_advice(bmi, sbp, dbp):
    try:
        bmi = float(bmi)
    except:
        bmi = None
    try:
        sbp = float(sbp)
        dbp = float(dbp)
    except:
        sbp = dbp = None

    # วิเคราะห์ BMI
    if bmi is None:
        bmi_text = ""
    elif bmi > 30:
        bmi_text = "น้ำหนักเกินมาตรฐานมาก"
    elif bmi >= 25:
        bmi_text = "น้ำหนักเกินมาตรฐาน"
    elif bmi < 18.5:
        bmi_text = "น้ำหนักน้อยกว่ามาตรฐาน"
    else:
        bmi_text = "น้ำหนักอยู่ในเกณฑ์ปกติ"

    # วิเคราะห์ความดัน
    if sbp is None or dbp is None:
        bp_text = ""
    elif sbp >= 160 or dbp >= 100:
        bp_text = "ความดันโลหิตอยู่ในระดับสูงมาก"
    elif sbp >= 140 or dbp >= 90:
        bp_text = "ความดันโลหิตอยู่ในระดับสูง"
    elif sbp >= 120 or dbp >= 80:
        bp_text = "ความดันโลหิตเริ่มสูง"
    else:
        bp_text = ""  # ❗ ถ้าปกติ = ไม่ต้องพูดถึง

    # สร้างคำแนะนำรวม
    if not bmi_text and not bp_text:
        return "ไม่พบข้อมูลเพียงพอในการประเมินสุขภาพ"

    if "ปกติ" in bmi_text and not bp_text:
        return "น้ำหนักอยู่ในเกณฑ์ดี ควรรักษาพฤติกรรมสุขภาพนี้ต่อไป"

    if not bmi_text and bp_text:
        return f"{bp_text} แนะนำให้ดูแลสุขภาพ และติดตามค่าความดันอย่างสม่ำเสมอ"

    if bmi_text and bp_text:
        return f"{bmi_text} และ {bp_text} แนะนำให้ปรับพฤติกรรมด้านอาหารและการออกกำลังกาย"

    return f"{bmi_text} แนะนำให้ดูแลเรื่องโภชนาการและการออกกำลังกายอย่างเหมาะสม"

# ==================== UI FORM ====================
st.markdown("<h1 style='text-align:center;'>ระบบรายงานผลตรวจสุขภาพ</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align:center; color:gray;'>- กลุ่มงานอาชีวเวชกรรม รพ.สันทราย -</h4>", unsafe_allow_html=True)

with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    id_card = col1.text_input("เลขบัตรประชาชน")
    hn = col2.text_input("HN")
    full_name = col3.text_input("ชื่อ-สกุล")
    submitted = st.form_submit_button("ค้นหา")

# ==================== BLOOD COLUMN MAPPING ====================
blood_columns_by_year = {
    y: {
        "FBS": f"FBS{y}",
        "Uric": f"Uric Acid{y}",
        "ALK": f"ALP{y}",
        "SGOT": f"SGOT{y}",
        "SGPT": f"SGPT{y}",
        "Cholesterol": f"CHOL{y}",
        "TG": f"TGL{y}",
        "HDL": f"HDL{y}",
        "LDL": f"LDL{y}",
        "BUN": f"BUN{y}",
        "Cr": f"Cr{y}",
        "GFR": f"GFR{y}",
    }
    for y in years
}

if submitted:
    query = df.copy()
    if id_card.strip():
        query = query[query["เลขบัตรประชาชน"] == id_card.strip()]
    if hn.strip():
        query = query[query["HN"] == hn.strip()]
    if full_name.strip():
        query = query[query["ชื่อ-สกุล"].str.strip() == full_name.strip()]
    if query.empty:
        st.error("❌ ไม่พบข้อมูล กรุณาตรวจสอบอีกครั้ง")
        st.session_state.pop("person", None)
    else:
        st.session_state["person"] = query.iloc[0]

from collections import defaultdict

cbc_columns_by_year = defaultdict(dict)

for year in range(61, 69):
    cbc_columns_by_year[year] = {
        "hb": f"Hb(%)" + str(year),
        "hct": f"HCT" + str(year),
        "wbc": f"WBC (cumm)" + str(year),
        "plt": f"Plt (/mm)" + str(year),
    }

    if year == 68:
        cbc_columns_by_year[year].update({
            "ne": "Ne (%)68",
            "ly": "Ly (%)68",
            "eo": "Eo68",
            "mo": "M68",
            "ba": "BA68",
            "rbc": "RBCmo68",
            "mcv": "MCV68",
            "mch": "MCH68",
            "mchc": "MCHC",
        })

# ==================== DISPLAY ====================
if "person" in st.session_state:
    person = st.session_state["person"]

    selected_year = st.selectbox(
        "📅 เลือกปีที่ต้องการดูผลตรวจรายงาน", 
        options=sorted(years, reverse=True),
        format_func=lambda y: f"พ.ศ. {y + 2500}"
    )
    selected_cols = columns_by_year[selected_year]

    def render_health_report(person, year_cols):
        sbp = person.get(year_cols["sbp"], "")
        dbp = person.get(year_cols["dbp"], "")
        pulse = person.get(year_cols["pulse"], "-")
        weight = person.get(year_cols["weight"], "-")
        height = person.get(year_cols["height"], "-")
        waist = person.get(year_cols["waist"], "-")
    
        bp_result = "-"
        if sbp and dbp:
            bp_val = f"{sbp}/{dbp} ม.ม.ปรอท"
            bp_desc = interpret_bp(sbp, dbp)
            bp_result = f"{bp_val} - {bp_desc}"
    
        pulse = f"{pulse} ครั้ง/นาที" if pulse != "-" else "-"
        weight = f"{weight} กก." if weight else "-"
        height = f"{height} ซม." if height else "-"
        waist = f"{waist} ซม." if waist else "-"
    
        try:
            weight_val = float(weight.replace(" กก.", "").strip())
            height_val = float(height.replace(" ซม.", "").strip())
            bmi_val = weight_val / ((height_val / 100) ** 2)
        except Exception as e:
            st.warning(f"❌ ไม่สามารถคำนวณ BMI ได้: {e}")
            bmi_val = None
    
        summary_advice = html.escape(combined_health_advice(bmi_val, sbp, dbp))
    
        return f"""
        <div style="font-size: 18px; line-height: 1.8; color: inherit; padding: 24px 8px;">
            <div style="text-align: center; font-size: 22px; font-weight: bold;">รายงานผลการตรวจสุขภาพ</div>
            <div style="text-align: center;">วันที่ตรวจ: {person.get('วันที่ตรวจ', '-')}</div>
            <div style="text-align: center; margin-top: 10px;">
                โรงพยาบาลสันทราย 201 หมู่ที่ 11 ถนน เชียงใหม่ - พร้าว<br>
                ตำบลหนองหาร อำเภอสันทราย เชียงใหม่ 50290 โทร 053 921 199 ต่อ 167
            </div>
            <hr style="margin: 24px 0;">
            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 32px; margin-bottom: 20px; text-align: center;">
                <div><b>ชื่อ-สกุล:</b> {person.get('ชื่อ-สกุล', '-')}</div>
                <div><b>อายุ:</b> {person.get('อายุ', '-')} ปี</div>
                <div><b>เพศ:</b> {person.get('เพศ', '-')}</div>
                <div><b>HN:</b> {person.get('HN', '-')}</div>
                <div><b>หน่วยงาน:</b> {person.get('หน่วยงาน', '-')}</div>
            </div>
            <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 32px; margin-bottom: 16px; text-align: center;">
                <div><b>น้ำหนัก:</b> {weight}</div>
                <div><b>ส่วนสูง:</b> {height}</div>
                <div><b>รอบเอว:</b> {waist}</div>
                <div><b>ความดันโลหิต:</b> {bp_result}</div>
                <div><b>ชีพจร:</b> {pulse}</div>
            </div>
            <div style="margin-top: 16px; text-align: center;">
                <b>คำแนะนำ:</b> {summary_advice}
            </div>
        </div>
        """

    st.markdown(render_health_report(person, selected_cols), unsafe_allow_html=True)

    # ================== CBC / BLOOD TEST DISPLAY ==================
    def generate_summary_advice(person, cbc_cols, blood_cols, sex):
        messages = []
    
        def abnormal(val, low=None, high=None, higher_is_better=False):
            try:
                val = float(str(val).replace(",", "").strip())
                if higher_is_better:
                    return "low" if val < low else "normal"
                if low is not None and val < low:
                    return "low"
                if high is not None and val > high:
                    return "high"
                return "normal"
            except:
                return None
    
        def highlight(label, value, tooltip):
            return f'<span title="{tooltip}">{label} ({value})</span>'
    
        hb = person.get(cbc_cols.get("hb"))
        hb_limit = 12 if sex == "หญิง" else 13
        if abnormal(hb, low=hb_limit) == "low":
            messages.append(f'🔸 {highlight("Hb ต่ำ", hb, "ควร >12 หญิง, >13 ชาย")} - เพิ่มธาตุเหล็ก')
    
        wbc = person.get(cbc_cols.get("wbc"))
        if abnormal(wbc, low=4000, high=10000):
            messages.append(f'🔸 {highlight("WBC ผิดปกติ", wbc, "ค่าปกติ 4,000 - 10,000")} - ดูแลสุขภาพ')
    
        plt = person.get(cbc_cols.get("plt"))
        if abnormal(plt, low=150000, high=500000):
            messages.append(f'🔸 {highlight("เกล็ดเลือดผิดปกติ", plt, "150,000 - 500,000")} - เฝ้าระวังเลือดออกง่าย')
    
        for label, col, low, high, tip, short in [
            ("Neutrophil", "ne", 43, 70, "43 - 70%", "ภูมิคุ้มกัน"),
            ("Lymphocyte", "ly", 20, 44, "20 - 44%", "ไวรัส"),
            ("Monocyte", "mo", 3, 9, "3 - 9%", "การอักเสบ"),
            ("Eosinophil", "eo", 0, 9, "0 - 9%", "ภูมิแพ้"),
            ("Basophil", "ba", 0, 3, "0 - 3%", "ภูมิแพ้"),
        ]:
            val = person.get(cbc_cols.get(col))
            if abnormal(val, low, high):
                messages.append(f'🔸 {highlight(f"{label} ผิดปกติ", val, f"ค่าปกติ {tip}")} - อาจเกี่ยวกับ{short}')
    
        for label, col, low, high, tip, rec, hib in [
            ("LDL", "LDL", None, 160, "ไม่ควรเกิน 160", "ลดไขมัน", False),
            ("HDL", "HDL", 40, None, "ควร > 40", "ออกกำลังกาย", True),
            ("Triglyceride", "TG", 35, 150, "35 - 150", "ลดของทอด", False),
            ("Cholesterol", "Cholesterol", 150, 200, "150 - 200", "คุมอาหาร", False),
            ("GFR", "GFR", 60, None, "> 60", "ดื่มน้ำ", True),
            ("Creatinine", "Cr", 0.5, 1.17, "0.5 - 1.17", "ติดตามไต", False),
            ("FBS", "FBS", 74, 106, "74 - 106", "ลดหวาน", False),
            ("SGOT", "SGOT", None, 37, "< 37", "พักผ่อน", False),
            ("SGPT", "SGPT", None, 41, "< 41", "ลดของทอด", False),
        ]:
            val = person.get(blood_cols.get(col))
            if abnormal(val, low, high, higher_is_better=hib):
                messages.append(f'🔸 {highlight(f"{label} ผิดปกติ", val, f"ค่าปกติ {tip}")} - {rec}')
    
        if not messages:
            return "✅ <span title='ไม่มีค่าที่อยู่นอกเกณฑ์'>ไม่พบค่าที่ผิดปกติ</span> สุขภาพอยู่ในเกณฑ์ดี ✅"
    
        return "<br>".join(messages) + "<br><br>📌 หากมีอาการผิดปกติควรปรึกษาแพทย์"

    st.markdown("### 🧪 รายงานผลตรวจเลือด")
    
    cbc_cols = cbc_columns_by_year[selected_year]
    blood_cols = blood_columns_by_year[selected_year]
    
    # ✅ ฟังก์ชันช่วยให้แสดงค่า และ flag ว่าผิดปกติหรือไม่
    def flag_value(raw, low=None, high=None, higher_is_better=False):
        try:
            val = float(str(raw).replace(",", "").strip())
            if higher_is_better:
                return f"{val:.1f}", val < low
            if (low is not None and val < low) or (high is not None and val > high):
                return f"{val:.1f}", True
            return f"{val:.1f}", False
        except:
            return "-", False
    
    # ✅ CBC config
    sex = person.get("เพศ", "").strip()
    hb_low = 12 if sex == "หญิง" else 13
    hct_low = 36 if sex == "หญิง" else 39
    
    cbc_config = [
        ("ฮีโมโกลบิน (Hb)", cbc_cols.get("hb"), "ชาย > 13, หญิง > 12 g/dl", hb_low, None),
        ("ฮีมาโทคริต (Hct)", cbc_cols.get("hct"), "ชาย > 39%, หญิง > 36%", hct_low, None),
        ("เม็ดเลือดขาว (wbc)", cbc_cols.get("wbc"), "4,000 - 10,000 /cu.mm", 4000, 10000),
        ("นิวโทรฟิล (Neutrophil)", cbc_cols.get("ne"), "43 - 70%", 43, 70),
        ("ลิมโฟไซต์ (Lymphocyte)", cbc_cols.get("ly"), "20 - 44%", 20, 44),
        ("โมโนไซต์ (Monocyte)", cbc_cols.get("mo"), "3 - 9%", 3, 9),
        ("อีโอซิโนฟิล (Eosinophil)", cbc_cols.get("eo"), "0 - 9%", 0, 9),
        ("เบโซฟิล (Basophil)", cbc_cols.get("ba"), "0 - 3%", 0, 3),
        ("เกล็ดเลือด (Platelet)", cbc_cols.get("plt"), "150,000 - 500,000 /cu.mm", 150000, 500000),
    ]
    
    cbc_rows = []
    for name, col, normal, low, high in cbc_config:
        raw = person.get(col, "-")
        result, is_abnormal = flag_value(raw, low, high)
        cbc_rows.append([(name, is_abnormal), (result, is_abnormal), (normal, is_abnormal)])
    
    # ✅ BLOOD config
    blood_config = [
        ("น้ำตาลในเลือด (FBS)", blood_cols["FBS"], "74 - 106 mg/dl", 74, 106),
        ("กรดยูริก (Uric Acid)", blood_cols["Uric"], "2.6 - 7.2 mg%", 2.6, 7.2),
        ("ALK.POS", blood_cols["ALK"], "30 - 120 U/L", 30, 120),
        ("SGOT", blood_cols["SGOT"], "&lt; 37 U/L", None, 37),
        ("SGPT", blood_cols["SGPT"], "&lt; 41 U/L", None, 41),
        ("Cholesterol", blood_cols["Cholesterol"], "150 - 200 mg/dl", 150, 200),
        ("Triglyceride", blood_cols["TG"], "35 - 150 mg/dl", 35, 150),
        ("HDL", blood_cols["HDL"], "&gt; 40 mg/dl", 40, None, True),
        ("LDL", blood_cols["LDL"], "0 - 160 mg/dl", 0, 160),
        ("BUN", blood_cols["BUN"], "7.9 - 20 mg/dl", 7.9, 20),
        ("Creatinine (Cr)", blood_cols["Cr"], "0.5 - 1.17 mg/dl", 0.5, 1.17),
        ("GFR", blood_cols["GFR"], "&gt; 60 mL/min", 60, None, True),
    ]
    
    blood_rows = []
    for name, col, normal, low, high, *opt in blood_config:
        higher_is_better = opt[0] if opt else False
        raw = person.get(col, "-")
        result, is_abnormal = flag_value(raw, low, high, higher_is_better=higher_is_better)
        blood_rows.append([(name, is_abnormal), (result, is_abnormal), (normal, is_abnormal)])
    
    # ✅ Styled table renderer
    def styled_result_table(headers, rows):
        header_html = "".join([f"<th>{h}</th>" for h in headers])
        html = f"""
        <style>
            .styled-result td {{
                padding: 6px 12px;
                vertical-align: middle;
            }}
            .styled-result th {{
                background-color: #111;
                color: white;
                padding: 6px 12px;
            }}
            .abn {{
                background-color: rgba(255, 0, 0, 0.15);
            }}
        </style>
        <table class='styled-result'>
            <thead><tr>{header_html}</tr></thead>
            <tbody>
        """
        for row in rows:
            row_html = ""
            for cell, is_abn in row:
                css = " class='abn'" if is_abn else ""
                row_html += f"<td{css}>{cell}</td>"
            html += f"<tr>{row_html}</tr>"
        html += "</tbody></table>"
        return html
    
    # ✅ Render ทั้งสองตาราง
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🩸 ผลการตรวจความสมบูรณ์ของเม็ดเลือด (CBC)")
        st.markdown(styled_result_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], cbc_rows), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### 💉 ผลตรวจเลือด (Blood Test)")
        st.markdown(styled_result_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], blood_rows), unsafe_allow_html=True)

    # ✅ แสดงคำแนะนำใหม่แบบสรุปอ่อนโยน
    summary = generate_summary_advice(person, cbc_cols, blood_cols, sex)
    st.markdown(f"""
    <div style='background-color:#2e0e0e33; padding:20px; border-left:6px solid #ff4d4d; border-radius:8px; margin-top:24px;'>
        <h4>📌 คำแนะนำโดยรวมจากผลตรวจ:</h4>
        {summary}
    </div>
    """, unsafe_allow_html=True)

