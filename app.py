import numpy as np
import streamlit as st
import pandas as pd
import gspread
import json
import matplotlib.pyplot as plt
from oauth2client.service_account import ServiceAccountCredentials

st.set_page_config(page_title="ระบบรายงานสุขภาพ", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Chakra+Petch&display=swap');

    html, body, [class*="css"] {
        font-family: 'Chakra Petch', sans-serif !important;
    }
    </style>
""", unsafe_allow_html=True)

# ===============================
# CONNECT GOOGLE SHEET (ปลอดภัยแม้เปลี่ยน sheet แรก)
# ===============================
try:
    service_account_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT"])
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    client = gspread.authorize(creds)

    sheet_url = "https://docs.google.com/spreadsheets/d/1N3l0o_Y6QYbGKx22323mNLPym77N0jkJfyxXFM2BDmc"
    worksheet = client.open_by_url(sheet_url).sheet1  # ✅ sheet แรกเสมอ

    raw_data = worksheet.get_all_records()  # ✅ พยายามอ่านข้อมูล
    if not raw_data:
        st.error("❌ ไม่พบข้อมูลในแผ่นแรกของ Google Sheet")
        st.stop()

    df = pd.DataFrame(raw_data)

    # ✅ ทำความสะอาดชื่อคอลัมน์และข้อมูลสำคัญ
    df.columns = df.columns.str.strip()
    df['เลขบัตรประชาชน'] = df['เลขบัตรประชาชน'].astype(str).str.strip()
    df['HN'] = df['HN'].astype(str).str.strip()
    df['ชื่อ-สกุล'] = df['ชื่อ-สกุล'].astype(str).str.strip()

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการโหลด Google Sheet: {e}")
    st.stop()
    
# ===============================
# YEAR MAPPING
# ===============================
years = list(range(61, 69))
columns_by_year = {
    year: {
        "weight": f"น้ำหนัก{year}" if year != 68 else "น้ำหนัก",
        "height": f"ส่วนสูง{year}" if year != 68 else "ส่วนสูง",
        "waist": f"รอบเอว{year}" if year != 68 else "รอบเอว",
        "sbp": f"SBP{year}" if year != 68 else "SBP",
        "dbp": f"DBP{year}" if year != 68 else "DBP",
        "pulse": f"pulse{year}" if year != 68 else "pulse",
        "bmi_value": f"BMI{year}" if year != 68 else "ดัชนีมวลกาย",
    }
    for year in years
}

# ===============================
# FUNCTIONS
# ===============================
def interpret_bmi(bmi):
    if bmi is None or bmi == "":
        return "-"
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
    except:
        return "-"

def interpret_waist(waist, height):
    try:
        waist = float(waist)
        height = float(height)
        return "เกินเกณฑ์" if waist > height else "ปกติ"
    except:
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
    except:
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

    hb = hb_result.strip()
    wbc = wbc_result.strip()
    plt = plt_result.strip()

    # ✅ Plt ต่ำต้องตรวจสอบก่อน เพราะสูตร Excel ให้ความสำคัญเป็นพิเศษ
    if plt in ["ต่ำกว่าเกณฑ์", "ต่ำกว่าเกณฑ์เล็กน้อย"]:
        return cbc_messages[4]

    if hb == "ปกติ" and wbc == "ปกติ" and plt == "ปกติ":
        return ""

    if hb == "พบภาวะโลหิตจาง" and wbc == "ปกติ" and plt == "ปกติ":
        return cbc_messages[8]

    if hb == "พบภาวะโลหิตจาง" and wbc in [
        "ต่ำกว่าเกณฑ์", 
        "ต่ำกว่าเกณฑ์เล็กน้อย", 
        "สูงกว่าเกณฑ์เล็กน้อย", 
        "สูงกว่าเกณฑ์"
    ]:
        return cbc_messages[9]

    if hb == "พบภาวะโลหิตจางเล็กน้อย" and wbc == "ปกติ" and plt == "ปกติ":
        return cbc_messages[2]

    if hb == "ปกติ" and wbc in [
        "ต่ำกว่าเกณฑ์", 
        "ต่ำกว่าเกณฑ์เล็กน้อย", 
        "สูงกว่าเกณฑ์เล็กน้อย", 
        "สูงกว่าเกณฑ์"
    ]:
        return cbc_messages[6]

    if plt == "สูงกว่าเกณฑ์":
        return cbc_messages[10]

    if hb == "พบภาวะโลหิตจางเล็กน้อย" and \
       wbc in [
           "ต่ำกว่าเกณฑ์", 
           "ต่ำกว่าเกณฑ์เล็กน้อย", 
           "สูงกว่าเกณฑ์เล็กน้อย", 
           "สูงกว่าเกณฑ์"
       ] and plt == "ปกติ":
        return cbc_messages[13]

    return "ควรพบแพทย์เพื่อตรวจเพิ่มเติม"

# ===============================
# UI SEARCH
# ===============================
st.markdown("<h1 style='text-align:center;'>ระบบรายงานผลตรวจสุขภาพ</h1>", unsafe_allow_html=True)
st.markdown("<h4 style='text-align:center; color:gray;'>- กลุ่มงานอาชีวเวชกรรม รพ.สันทราย -</h4>", unsafe_allow_html=True)

with st.form("search_form"):
    col1, col2, col3 = st.columns(3)
    id_card = col1.text_input("เลขบัตรประชาชน")
    hn = col2.text_input("HN")
    full_name = col3.text_input("ชื่อ-สกุล")
    submitted = st.form_submit_button("ค้นหา")  # ✅ สร้างตัวแปรตรงนี้เท่านั้น!

# ✅ หลังจาก form เสร็จแล้ว ถึงใช้ได้
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
        if "person" in st.session_state:
            del st.session_state["person"]  # 👈 ล้างข้อมูลเก่าทันที

    else:
        st.session_state["person"] = query.iloc[0]

# ===============================
# DISPLAY
# ===============================
if "person" in st.session_state:
    person = st.session_state["person"]

    # เตรียมค่าที่ต้องใช้
    # ===== ปีล่าสุด (2568) =====
    bp_sbp = person.get("SBP", "")
    bp_dbp = person.get("DBP", "")
    
    # ความดันโลหิตค่าตัวเลข
    if bp_sbp and bp_dbp:
        bp_numeric = f"{bp_sbp}/{bp_dbp} ม.ม.ปรอท"
        bp_meaning = interpret_bp(bp_sbp, bp_dbp)
        bp_result = f"{bp_numeric} - {bp_meaning}"
    else:
        bp_result = "-"

    bp_result = f"{bp_result} ม.ม.ปรอท" if bp_result != "-" else "-"
    pulse_value = person.get("pulse", "-")
    pulse_value = f"{pulse_value} ครั้ง/นาที" if pulse_value != "-" else "-"

    st.markdown(f"""
    <div style='
        max-width: 800px;
        margin: auto;
        background-color: #f8f9fa;
        padding: 30px;
        border-radius: 12px;
        border: 1px solid #ccc;
        color: black;
        font-size: 16px;
        line-height: 1.8;
    '>
        <div style='text-align: center; font-size: 22px; font-weight: bold; margin-bottom: 5px;'>รายงานผลการตรวจสุขภาพ</div>
        <div style='text-align: center; font-size: 16px;'>วันที่ตรวจ: {person.get('วันที่ตรวจ', '-')}</div>
    
        <div style='text-align: center; margin-top: 10px;'>
            โรงพยาบาลสันทราย 201 หมู่ที่ 11 ถนน เชียงใหม่ - พร้าว<br>
            ตำบลหนองหาร อำเภอสันทราย เชียงใหม่ 50290 โทร 053 921 199 ต่อ 167
        </div>
    
        <hr style='margin: 24px 0;'>
    
        <div style='display: flex; flex-wrap: wrap; justify-content: space-between; margin-bottom: 16px;'>
            <div><b>ชื่อ-สกุล:</b> {person.get('ชื่อ-สกุล', '-')}</div>
            <div><b>อายุ:</b> {person.get('อายุ', '-')} ปี</div>
            <div><b>เพศ:</b> {person.get('เพศ', '-')}</div>
            <div><b>HN:</b> {person.get('HN', '-')}</div>
            <div><b>หน่วยงาน:</b> {person.get('หน่วยงาน', '-')}</div>
        </div>
    
        <div style='display: flex; flex-wrap: wrap; justify-content: space-between;'>
            <div><b>ความดันโลหิต:</b> {bp_result}</div>
            <div><b>ชีพจร:</b> {pulse_value}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ✅ สร้างตารางข้อมูลสุขภาพตามปี
    table_data = {
        "ปี พ.ศ.": [],
        "น้ำหนัก (กก.)": [],
        "ส่วนสูง (ซม.)": [],  # ✅ เพิ่มตรงนี้
        "รอบเอว (ซม.)": [],
        "ความดัน (mmHg)": [],
        "BMI (แปลผล)": []
    }
    
    for y in sorted(years):
        cols = columns_by_year[y]  # ✅ ต้องมี
        weight = person.get(cols["weight"], "")
        height = person.get(cols["height"], "")
        waist = person.get(cols["waist"], "")
        sbp = person.get(cols["sbp"], "")
        dbp = person.get(cols["dbp"], "")
    
        # ✅ คำนวณ BMI จากน้ำหนักและส่วนสูง
        try:
            bmi_val = float(weight) / ((float(height) / 100) ** 2)
            bmi_val = round(bmi_val, 1)
            bmi_str = f"{bmi_val}<br><span style='font-size: 13px; color: gray;'>{interpret_bmi(bmi_val)}</span>"
        except:
            bmi_val = None
            bmi_str = "-"
    
        # ✅ แปลผลความดัน
        try:
            if sbp or dbp:
                bp_val = f"{sbp}/{dbp}"
                bp_meaning = interpret_bp(sbp, dbp)
                bp_str = f"{bp_val}<br><span style='font-size: 13px; color: gray;'>{bp_meaning}</span>"
            else:
                bp_str = "-"
        except:
            bp_str = "-"
    
        # ✅ เติมข้อมูลลงตาราง
        table_data["ปี พ.ศ."].append(y + 2500)
        table_data["น้ำหนัก (กก.)"].append(weight if weight else "-")
        table_data["ส่วนสูง (ซม.)"].append(height if height else "-")
        table_data["รอบเอว (ซม.)"].append(waist if waist else "-")
        table_data["ความดัน (mmHg)"].append(bp_str)
        table_data["BMI (แปลผล)"].append(bmi_str)
    
    # ✅ แสดงผลตาราง (รองรับ HTML <br> ด้วย unsafe_allow_html)
    st.markdown("### 📊 น้ำหนัก / รอบเอว / ความดัน")
    html_table = pd.DataFrame(table_data).set_index("ปี พ.ศ.").T.to_html(escape=False)
    st.markdown(html_table, unsafe_allow_html=True)

    # ==========================
    # GRAPH: BMI History
    # ==========================

    bmi_data = []
    labels = []

    for y in sorted(years):
        cols = columns_by_year[y]  # ✅ ต้องอยู่ในลูปเท่านั้น!

        weight = person.get(cols["weight"], "")
        height = person.get(cols["height"], "")

        try:
            weight = float(weight)
            height = float(height)
            if weight > 0 and height > 0:
                bmi_val = round(weight / ((height / 100) ** 2), 1)
                bmi_data.append(bmi_val)
                labels.append(f"B.E. {y + 2500}")
        except:
            continue

    if bmi_data and labels:
        st.markdown("### 📈 BMI Trend")
        fig, ax = plt.subplots(figsize=(10, 4))
        
        ax.axhspan(30, 40, facecolor='#D32F2F', alpha=0.3, label='Severely Obese')
        ax.axhspan(25, 30, facecolor='#FF5722', alpha=0.3, label='Obese')
        ax.axhspan(23, 25, facecolor='#FF9900', alpha=0.3, label='Overweight')
        ax.axhspan(18.5, 23, facecolor='#109618', alpha=0.3, label='Normal')
        ax.axhspan(0, 18.5, facecolor='#3366CC', alpha=0.3, label='Underweight')

        ax.plot(np.arange(len(labels)), bmi_data, marker='o', color='black', linewidth=2, label='BMI')
        ax.set_xticks(np.arange(len(labels)))
        ax.set_xticklabels(labels)
        ax.set_ylabel("BMI", fontsize=12)
        ax.set_ylim(15, 40)
        ax.set_title("BMI Over Time", fontsize=14)
        ax.legend(loc="upper left")

        st.pyplot(fig)
    else:
        st.info("ไม่มีข้อมูล BMI เพียงพอสำหรับแสดงกราฟ")
