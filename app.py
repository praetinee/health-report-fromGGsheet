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
        ("กรดยูริคสาเหตุโรคเก๊าท์ (Uric acid)", blood_cols["Uric"], "2.6 - 7.2 mg%", 2.6, 7.2),
        ("การทำงานของเอนไซม์ตับ ALK.POS", blood_cols["ALK"], "30 - 120 U/L", 30, 120),
        ("การทำงานของเอนไซม์ตับ SGOT", blood_cols["SGOT"], "&lt; 37 U/L", None, 37),
        ("การทำงานของเอนไซม์ตับ SGPT", blood_cols["SGPT"], "&lt; 41 U/L", None, 41),
        ("คลอเรสเตอรอล (Cholesterol)", blood_cols["Cholesterol"], "150 - 200 mg/dl", 150, 200),
        ("ไตรกลีเซอไรด์ (Triglyceride)", blood_cols["TG"], "35 - 150 mg/dl", 35, 150),
        ("ไขมันดี (HDL)", blood_cols["HDL"], "&gt; 40 mg/dl", 40, None, True),
        ("ไขมันเลว (LDL)", blood_cols["LDL"], "0 - 160 mg/dl", 0, 160),
        ("การทำงานของไต (BUN)", blood_cols["BUN"], "7.9 - 20 mg/dl", 7.9, 20),
        ("การทำงานของไต (Cr)", blood_cols["Cr"], "0.5 - 1.17 mg/dl", 0.5, 1.17),
        ("ประสิทธิภาพการกรองของไต (GFR)", blood_cols["GFR"], "&gt; 60 mL/min", 60, None, True),
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
    left_spacer, col1, col2, right_spacer = st.columns([1, 3, 3, 1])
    
    with col1:
        st.markdown("#### 🩸 ผลการตรวจความสมบูรณ์ของเม็ดเลือด (CBC)")
        st.markdown(styled_result_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], cbc_rows), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### 💉 ผลตรวจเลือด (Blood Test)")
        st.markdown(styled_result_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], blood_rows), unsafe_allow_html=True)

    import re
    
    # 📌 ฟังก์ชันรวมคำแนะนำแบบไม่ซ้ำซ้อน
    def merge_similar_sentences(messages):
        if len(messages) == 1:
            return messages[0]
    
        merged = []
        seen_prefixes = {}
    
        for msg in messages:
            prefix = re.match(r"^(ควรพบแพทย์เพื่อตรวจหา(?:และติดตาม)?(?:[^,]*)?)", msg)
            if prefix:
                key = "ควรพบแพทย์เพื่อตรวจหา"
                rest = msg[len(prefix.group(1)):].strip()
                phrase = prefix.group(1)[len(key):].strip()
    
                # 🔧 รวม phrase และ rest → แล้วลบ "และ" ที่ขึ้นต้น
                full_detail = f"{phrase} {rest}".strip()
                full_detail = re.sub(r"^และ\s+", "", full_detail)
    
                if key in seen_prefixes:
                    seen_prefixes[key].append(full_detail)
                else:
                    seen_prefixes[key] = [full_detail]
            else:
                merged.append(msg)
    
        for key, endings in seen_prefixes.items():
            endings = [e.strip() for e in endings if e]
            if endings:
                if len(endings) == 1:
                    merged.append(f"{key} {endings[0]}")
                else:
                    body = " ".join(endings[:-1]) + " และ " + endings[-1]
                    merged.append(f"{key} {body}")
            else:
                merged.append(key)
    
        return "<br>".join(merged)
    
    cbc_messages = {
        2:  "ดูแลสุขภาพ ออกกำลังกาย ทานอาหารมีประโยชน์ ติดตามผลเลือดสม่ำเสมอ",
        4:  "ควรพบแพทย์เพื่อตรวจหาสาเหตุเกล็ดเลือดต่ำ เพื่อเฝ้าระวังอาการผิดปกติ",
        6:  "ควรตรวจซ้ำเพื่อติดตามเม็ดเลือดขาว และดูแลสุขภาพร่างกายให้แข็งแรง",
        8:  "ควรพบแพทย์เพื่อตรวจหาสาเหตุภาวะโลหิตจาง เพื่อรักษาตามนัด",
        9:  "ควรพบแพทย์เพื่อตรวจหาและติดตามภาวะโลหิตจางร่วมกับเม็ดเลือดขาวผิดปกติ",
        10: "ควรพบแพทย์เพื่อตรวจหาสาเหตุเกล็ดเลือดสูง เพื่อพิจารณาการรักษา",
        13: "ควรดูแลสุขภาพ ติดตามภาวะโลหิตจางและเม็ดเลือดขาวผิดปกติอย่างใกล้ชิด",
    }
    
    def interpret_wbc(wbc):
        try:
            wbc = float(wbc)
            if wbc == 0:
                return "-"
            elif 4000 <= wbc <= 10000:
                return "ปกติ"
            elif 10000 < wbc < 13000:
                return "สูงกว่าเกณฑ์เล็กน้อย"
            elif wbc >= 13000:
                return "สูงกว่าเกณฑ์"
            elif 3000 < wbc < 4000:
                return "ต่ำกว่าเกณฑ์เล็กน้อย"
            elif wbc <= 3000:
                return "ต่ำกว่าเกณฑ์"
        except:
            return "-"
        return "-"
    
    def interpret_hb(hb, sex):
        try:
            hb = float(hb)
            if sex == "ชาย":
                if hb < 12:
                    return "พบภาวะโลหิตจาง"
                elif 12 <= hb < 13:
                    return "พบภาวะโลหิตจางเล็กน้อย"
                else:
                    return "ปกติ"
            elif sex == "หญิง":
                if hb < 11:
                    return "พบภาวะโลหิตจาง"
                elif 11 <= hb < 12:
                    return "พบภาวะโลหิตจางเล็กน้อย"
                else:
                    return "ปกติ"
        except:
            return "-"
        return "-"
    
    def interpret_plt(plt):
        try:
            plt = float(plt)
            if plt == 0:
                return "-"
            elif 150000 <= plt <= 500000:
                return "ปกติ"
            elif 500000 < plt < 600000:
                return "สูงกว่าเกณฑ์เล็กน้อย"
            elif plt >= 600000:
                return "สูงกว่าเกณฑ์"
            elif 100000 <= plt < 150000:
                return "ต่ำกว่าเกณฑ์เล็กน้อย"
            elif plt < 100000:
                return "ต่ำกว่าเกณฑ์"
        except:
            return "-"
        return "-"
    
    def cbc_advice(hb_result, wbc_result, plt_result):
        message_ids = []
    
        if all(x in ["", "-", None] for x in [hb_result, wbc_result, plt_result]):
            return "-"
    
        if hb_result == "พบภาวะโลหิตจาง":
            if wbc_result == "ปกติ" and plt_result == "ปกติ":
                message_ids.append(8)
            elif wbc_result in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"]:
                message_ids.append(9)
        elif hb_result == "พบภาวะโลหิตจางเล็กน้อย":
            if wbc_result == "ปกติ" and plt_result == "ปกติ":
                message_ids.append(2)
            elif wbc_result in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"]:
                message_ids.append(13)
    
        if wbc_result in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"] and hb_result == "ปกติ":
            message_ids.append(6)
    
        if plt_result == "สูงกว่าเกณฑ์":
            message_ids.append(10)
        elif plt_result in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย"]:
            message_ids.append(4)
    
        if not message_ids and hb_result == "ปกติ" and wbc_result == "ปกติ" and plt_result == "ปกติ":
            return ""
    
        if not message_ids:
            return "ควรพบแพทย์เพื่อตรวจเพิ่มเติม"
    
        # รวมข้อความจากหลาย id
        raw_msgs = [cbc_messages[i] for i in sorted(set(message_ids))]
        return merge_similar_sentences(raw_msgs)
    
    # 🔧 ยึดปีจาก selectbox
    suffix = str(selected_year)
    sex = person.get("เพศ", "").strip()
    
    # 🔍 ดึงค่าตามปีที่เลือก
    hb_raw = str(person.get(f"Hb(%)" + suffix, "")).strip()
    wbc_raw = str(person.get(f"WBC (cumm)" + suffix, "")).strip()
    plt_raw = str(person.get(f"Plt (/mm)" + suffix, "")).strip()
    
    # 🧠 แปลผล
    hb_result = interpret_hb(hb_raw, sex)
    wbc_result = interpret_wbc(wbc_raw)
    plt_result = interpret_plt(plt_raw)
    
    # 🩺 คำแนะนำ
    recommendation = cbc_advice(hb_result, wbc_result, plt_result)
    
    # ✅ แสดงเฉพาะปีที่เลือก
    if recommendation and not all(x == "-" for x in [hb_result, wbc_result, plt_result]):
        st.markdown(f"""
        <div style='
            background-color: rgba(255, 105, 135, 0.15);
            padding: 1rem;
            border-radius: 6px;
            color: white;
            margin-top: 1rem;
        '>
            <div style='font-size: 18px; font-weight: bold;'>📌 คำแนะนำผลตรวจเลือด (CBC) ปี {2500 + selected_year}</div>
            <div style='font-size: 16px; margin-top: 0.3rem;'>{recommendation}</div>
        </div>
        """, unsafe_allow_html=True)

    def summarize_liver(alp_val, sgot_val, sgpt_val):
        try:
            alp = float(alp_val)
            sgot = float(sgot_val)
            sgpt = float(sgpt_val)
            if alp == 0 or sgot == 0 or sgpt == 0:
                return "-"
            if alp > 120 or sgot > 36 or sgpt > 40:
                return "การทำงานของตับสูงกว่าเกณฑ์ปกติเล็กน้อย"
            return "ปกติ"
        except:
            return "-"
    
    def liver_advice(summary_text):
        if summary_text == "การทำงานของตับสูงกว่าเกณฑ์ปกติเล็กน้อย":
            return "ควรลดอาหารไขมันสูงและตรวจติดตามการทำงานของตับซ้ำ"
        elif summary_text == "ปกติ":
            return ""
        return "-"
    
    # ✅ ใช้ปีที่เลือกจาก dropdown
    y = selected_year
    y_label = "" if y == 2568 else str(y % 100)
    
    alp_raw = str(person.get(f"ALP{y_label}", "") or "").strip()
    sgot_raw = str(person.get(f"SGOT{y_label}", "") or "").strip()
    sgpt_raw = str(person.get(f"SGPT{y_label}", "") or "").strip()
    
    summary = summarize_liver(alp_raw, sgot_raw, sgpt_raw)
    advice_liver = liver_advice(summary)
    
    if advice_liver and advice_liver != "-" and summary != "-":
        st.markdown(f"""
        <div style='
            background-color: rgba(100, 221, 23, 0.15);
            padding: 1rem;
            border-radius: 6px;
            color: white;
            margin-top: 1rem;
        '>
            <div style='font-size: 18px; font-weight: bold;'>📌 คำแนะนำผลตรวจตับ ปี {2500 + selected_year}</div>
            <div style='font-size: 16px; margin-top: 0.3rem;'>{advice_liver}</div>
        </div>
        """, unsafe_allow_html=True)

    def uric_acid_advice(value_raw):
        try:
            value = float(value_raw)
            if value > 7.2:
                return "ควรลดอาหารที่มีพิวรีนสูง เช่น เครื่องในสัตว์ อาหารทะเล และพบแพทย์หากมีอาการปวดข้อ"
            return ""
        except:
            return "-"
    
    # ✅ ปีที่เลือกจาก dropdown
    y = selected_year
    y_label = "" if y == 2568 else str(y % 100)
    col_name = f"Uric Acid{y_label}"
    
    raw_value = str(person.get(col_name, "") or "").strip()
    advice_uric = uric_acid_advice(raw_value)
    
    if advice_uric and advice_uric != "-":
        st.markdown(f"""
        <div style='
            background-color: rgba(245, 124, 0, 0.15);
            padding: 1rem;
            border-radius: 6px;
            color: white;
            margin-top: 1rem;
        '>
            <div style='font-size: 18px; font-weight: bold;'>📌 คำแนะนำกรดยูริคในเลือด ปี {2500 + selected_year}</div>
            <div style='font-size: 16px; margin-top: 0.3rem;'>{advice_uric}</div>
        </div>
        """, unsafe_allow_html=True)

    # 🧪 แปลผลการทำงานของไตจาก GFR
    def kidney_summary_gfr_only(gfr_raw):
        try:
            gfr = float(str(gfr_raw).replace(",", "").strip())
            if gfr == 0:
                return ""
            elif gfr < 60:
                return "การทำงานของไตต่ำกว่าเกณฑ์ปกติเล็กน้อย"
            else:
                return "ปกติ"
        except:
            return ""
    
    # 📌 คำแนะนำเมื่อพบค่าผิดปกติ
    def kidney_advice_from_summary(summary_text):
        if summary_text == "การทำงานของไตต่ำกว่าเกณฑ์ปกติเล็กน้อย":
            return (
                "การทำงานของไตต่ำกว่าเกณฑ์ปกติเล็กน้อย "
                "ลดอาหารเค็ม อาหารโปรตีนสูงย่อยยาก ดื่มน้ำ 8-10 แก้วต่อวัน "
                "และไม่ควรกลั้นปัสสาวะ มีอาการบวมผิดปกติให้พบแพทย์"
            )
        return ""
    # ✅ ดึงค่าจาก person ตามปีที่เลือก
    gfr_raw = str(person.get(f"GFR{y_label}", "") or "").strip()
    
    # ✅ วิเคราะห์ผลการทำงานของไต และให้คำแนะนำ
    kidney_summary = kidney_summary_gfr_only(gfr_raw)
    advice_kidney = kidney_advice_from_summary(kidney_summary)
    
    # ✅ แสดงคำแนะนำ
    if advice_kidney:
        st.markdown(f"""
        <div style='
            background-color: rgba(0, 188, 212, 0.15);
            padding: 1rem;
            border-radius: 6px;
            color: white;
            margin-top: 1rem;
        '>
            <div style='font-size: 18px; font-weight: bold;'>📌 คำแนะนำผลตรวจไต ปี {2500 + selected_year}</div>
            <div style='font-size: 16px; margin-top: 0.3rem;'>{advice_kidney}</div>
        </div>
        """, unsafe_allow_html=True)

    # ===============================
    # ✅ คำแนะนำผลน้ำตาลในเลือด (FBS)
    # ===============================
    
    def fbs_advice(fbs_raw):
        try:
            value = float(str(fbs_raw).replace(",", "").strip())
            if value == 0:
                return ""
            elif 100 <= value < 106:
                return "ระดับน้ำตาลเริ่มสูงเล็กน้อย ควรปรับพฤติกรรมการบริโภคอาหารหวาน แป้ง และออกกำลังกาย"
            elif 106 <= value < 126:
                return "ระดับน้ำตาลสูงเล็กน้อย ควรลดอาหารหวาน แป้ง ของมัน ตรวจติดตามน้ำตาลซ้ำ และออกกำลังกายสม่ำเสมอ"
            elif value >= 126:
                return "ระดับน้ำตาลสูง ควรพบแพทย์เพื่อตรวจยืนยันเบาหวาน และติดตามอาการ"
            else:
                return ""
        except:
            return ""
    
    # ใช้ปีที่เลือกจาก dropdown
    y = selected_year
    y_label = "" if y == 68 else str(y)
    col_name = f"FBS{y_label}"
    raw_value = str(person.get(col_name, "") or "").strip()
    advice_fbs = fbs_advice(raw_value)
    
    if advice_fbs:
        st.markdown(f"""
        <div style='
            background-color: rgba(255, 202, 40, 0.15);
            padding: 1rem;
            border-radius: 6px;
            color: white;
            margin-top: 1rem;
        '>
            <div style='font-size: 18px; font-weight: bold;'>📌 คำแนะนำระดับน้ำตาลในเลือด ปี {2500 + selected_year}</div>
            <div style='font-size: 16px; margin-top: 0.3rem;'>{advice_fbs}</div>
        </div>
        """, unsafe_allow_html=True)
