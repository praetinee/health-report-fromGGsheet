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

# 🩸 ข้อความคำแนะนำ CBC แบบกระชับ
cbc_messages = {
    2:  "ดูแลสุขภาพ ออกกำลังกาย ทานอาหารมีประโยชน์ ติดตามผลเลือดสม่ำเสมอ",
    4:  "ควรพบแพทย์เพื่อตรวจหาสาเหตุเกล็ดเลือดต่ำ และเฝ้าระวังอาการผิดปกติ",
    6:  "ควรตรวจซ้ำเพื่อติดตามเม็ดเลือดขาว และดูแลสุขภาพร่างกายให้แข็งแรง",
    8:  "ควรพบแพทย์เพื่อตรวจหาสาเหตุภาวะโลหิตจาง และรักษาตามนัด",
    9:  "ควรพบแพทย์เพื่อตรวจหาและติดตามภาวะโลหิตจางร่วมกับเม็ดเลือดขาวผิดปกติ",
    10: "ควรพบแพทย์เพื่อตรวจหาสาเหตุเกล็ดเลือดสูง และพิจารณาการรักษา",
    13: "ควรดูแลสุขภาพ ติดตามภาวะโลหิตจางและเม็ดเลือดขาวผิดปกติอย่างใกล้ชิด",
}

# 🩸 ฟังก์ชันให้คำแนะนำ CBC (ตามสูตร Excel)
def cbc_advice(hb_result, wbc_result, plt_result):
    if all(x in ["", "-", None] for x in [hb_result, wbc_result, plt_result]):
        return "-"

    hb = str(hb_result).strip()
    wbc = str(wbc_result).strip()
    plt = str(plt_result).strip()

    if plt in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย"]:
        return cbc_messages[4]

    if hb == "ปกติ" and wbc == "ปกติ" and plt == "ปกติ":
        return ""

    if hb == "พบภาวะโลหิตจาง" and wbc == "ปกติ" and plt == "ปกติ":
        return cbc_messages[8]

    if hb == "พบภาวะโลหิตจาง" and wbc in [
        "ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"
    ]:
        return cbc_messages[9]

    if hb == "พบภาวะโลหิตจางเล็กน้อย" and wbc == "ปกติ" and plt == "ปกติ":
        return cbc_messages[2]

    if hb == "ปกติ" and wbc in [
        "ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"
    ]:
        return cbc_messages[6]

    if plt == "สูงกว่าเกณฑ์":
        return cbc_messages[10]

    if hb == "พบภาวะโลหิตจางเล็กน้อย" and \
       wbc in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์เล็กน้อย", "สูงกว่าเกณฑ์"] and plt == "ปกติ":
        return cbc_messages[13]

    return "ควรพบแพทย์เพื่อตรวจเพิ่มเติม"


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
    
    # เพศมีผลต่อเกณฑ์ Hb / Hct
    sex = person.get("เพศ", "").strip()
    hb_low = 12 if sex == "หญิง" else 13
    hct_low = 36 if sex == "หญิง" else 39
    
    # ตรวจผิดปกติแล้วไฮไลต์
    def flag_result(value, low=None, high=None, higher_is_better=False):
        try:
            if value in ["", "-", None]:
                return "-", False, False
            val = float(str(value).replace(",", "").strip())
            low_flag = (low is not None and val < low)
            high_flag = (high is not None and val > high)
            better_flag = higher_is_better and low_flag
            is_abnormal = low_flag or high_flag or better_flag
            flag = " ⬇" if low_flag else " ⬆" if high_flag else ""
            return f"{val:.1f}{flag}", is_abnormal, True
        except:
            return "-", False, False
    
    def styled_table(headers, rows, abnormal_flags):
        style = """
        <style>
            .styled-table td, .styled-table th {
                padding: 6px 12px;
                border: 1px solid #ccc;
            }
            .styled-table tr:nth-child(even) { background-color: #f9f9f9; }
            .styled-table .abnormal {
                background-color: rgba(255, 0, 0, 0.2);
                font-weight: bold;
            }
        </style>
        """
        html = style + "<table class='styled-table'>"
        html += "<thead><tr>" + "".join(f"<th>{col}</th>" for col in headers) + "</tr></thead><tbody>"
        for row, abn in zip(rows, abnormal_flags):
            tr_class = "abnormal" if abn else ""
            html += f"<tr class='{tr_class}'>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        html += "</tbody></table>"
        return html
    
    # === CBC DATA ===
    cbc_tests = [
        ("ฮีโมโกลบิน (Hb)", "hb", hb_low, None, "ชาย &gt; 13, หญิง &gt; 12 g/dl"),
        ("ฮีมาโทคริต (Hct)", "hct", hct_low, None, "ชาย &gt; 39%, หญิง &gt; 36%"),
        ("เม็ดเลือดขาว (wbc)", "wbc", 4000, 10000, "4,000 - 10,000 /cu.mm"),
        ("นิวโทรฟิล (Neutrophil)", "ne", 43, 70, "43 - 70%"),
        ("ลิมโฟไซต์ (Lymphocyte)", "ly", 20, 44, "20 - 44%"),
        ("โมโนไซต์ (Monocyte)", "mo", 3, 9, "3 - 9%"),
        ("อีโอซิโนฟิล (Eosinophil)", "eo", 0, 9, "0 - 9%"),
        ("เบโซฟิล (Basophil)", "ba", 0, 3, "0 - 3%"),
        ("เกล็ดเลือด (Platelet)", "plt", 150000, 500000, "150,000 - 500,000 /cu.mm"),
    ]
    
    cbc_rows, cbc_flags = [], []
    cbc_summary_check = {}
    for label, key, low, high, normal in cbc_tests:
        val = person.get(cbc_cols.get(key), "")
        result, is_abnormal, has_data = flag_result(val, low, high)
        cbc_rows.append((label, result, normal))
        cbc_flags.append(is_abnormal)
        cbc_summary_check[key] = result if has_data else "-"
    
    # === BLOOD TEST DATA ===
    blood_tests = [
        ("น้ำตาลในเลือด (FBS)", "FBS", 74, 106, "74 - 106 mg/dl"),
        ("กรดยูริก (Uric Acid)", "Uric", 2.6, 7.2, "2.6 - 7.2 mg%"),
        ("ALK.POS", "ALK", 30, 120, "30 - 120 U/L"),
        ("SGOT", "SGOT", None, 37, "&lt; 37 U/L"),
        ("SGPT", "SGPT", None, 41, "&lt; 41 U/L"),
        ("Cholesterol", "Cholesterol", 150, 200, "150 - 200 mg/dl"),
        ("Triglyceride", "TG", 35, 150, "35 - 150 mg/dl"),
        ("HDL", "HDL", 40, None, "&gt; 40 mg/dl", True),
        ("LDL", "LDL", 0, 160, "0 - 160 mg/dl"),
        ("BUN", "BUN", 7.9, 20, "7.9 - 20 mg/dl"),
        ("Creatinine (Cr)", "Cr", 0.5, 1.17, "0.5 - 1.17 mg/dl"),
        ("GFR", "GFR", 60, None, "&gt; 60 mL/min", True),
    ]
    
    blood_rows, blood_flags = [], []
    for item in blood_tests:
        if len(item) == 6:
            label, key, low, high, normal, better_high = item
        else:
            label, key, low, high, normal = item
            better_high = False
        val = person.get(blood_cols.get(key), "")
        result, is_abnormal, _ = flag_result(val, low, high, higher_is_better=better_high)
        blood_rows.append((label, result, normal))
        blood_flags.append(is_abnormal)
    
    # === DISPLAY ===
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 🩸 ผลการตรวจความสมบูรณ์ของเม็ดเลือด (Complete Blood Count)")
        st.markdown(styled_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], cbc_rows, cbc_flags), unsafe_allow_html=True)
    
    with col2:
        st.markdown("#### 💉 ผลตรวจเลือด (Blood Test)")
        st.markdown(styled_table(["ชื่อการตรวจ", "ผลตรวจ", "ค่าปกติ"], blood_rows, blood_flags), unsafe_allow_html=True)
    
    # === คำแนะนำจากผล CBC (ใช้คอลัมน์ตามสูตร)
    hb_result = cbc_summary_check.get("hb", "-")
    wbc_result = cbc_summary_check.get("wbc", "-")
    plt_result = cbc_summary_check.get("plt", "-")
    cbc_summary = cbc_advice(hb_result, wbc_result, plt_result)
    
    if cbc_summary and cbc_summary != "-":
        st.markdown(f"<div style='margin-top:12px; color:#f33; font-weight:bold;'>📌 คำแนะนำจากผล CBC: {cbc_summary}</div>", unsafe_allow_html=True)


