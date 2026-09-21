import os
import re
import fitz  # PyMuPDF
import unicodedata
import pandas as pd
from PyPDF2 import PdfReader
from pathlib import Path

# الإعدادات الافتراضية
DEFAULT_INPUT_ROOT = 'input'
DEFAULT_OUTPUT_FOLDER = 'WOs output'
DEFAULT_OUTPUT_FILENAME = 'unified_extracted_data.xlsx'

# ------------------------------------------------------------------
# 1. أدوات استخراج النصوص (Text Extraction Engines)
# ------------------------------------------------------------------

def extract_text_gpon_style(file_path: str) -> str:
    """استخراج النصوص باستخدام PyMuPDF (مناسب لملفات GPON)."""
    try:
        doc = fitz.open(file_path)
        text_parts = []
        for page in doc:
            extracted = page.get_text('text')
            if extracted:
                text_parts.append(extracted)
            else:
                # Fallback to rawdict for complex layouts
                raw = page.get_text('rawdict') or {}
                for block in raw.get('blocks') or []:
                    for line in block.get('lines') or []:
                        for span in line.get('spans') or []:
                            t = span.get('text')
                            if t: text_parts.append(t + " ")
        text = ''.join(text_parts)
        return text.replace('\u200f', '').replace('\u200e', '')
    except Exception as e:
        print(f"Error reading {file_path} (Fitz): {e}")
        return ''

def extract_text_fiber_style(file_path: str) -> str:
    """استخراج النصوص باستخدام PyPDF2 (مناسب لملفات Fiber)."""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted: text += extracted + "\n"
        text = re.sub(r'[\u200f\u200e\u200b\u00a0\r]+', ' ', text)
        return unicodedata.normalize('NFKC', text)
    except Exception as e:
        print(f"Error reading {file_path} (PyPDF2): {e}")
        return ""

# ------------------------------------------------------------------
# 2. معالجات البيانات (Data Parsers)
# ------------------------------------------------------------------

def parse_gpon_data(text: str) -> dict:
    """منطق استخراج البيانات لملفات GPON."""
    data = {'Mode': 'GPON', 'Circuit Number': None, 'shelf': None, 'card': None, 'port': None, 
            'ONT ID': None, 'ONU Serial No': None, 'CST name': None, 'MSAN Code': None, 
            'Splitter': None, 'OLT Name': None, 'Speed': None}

    m = re.search(r'ONU Serial No\s*[:：]?\s*([A-Fa-f0-9]+)', text)
    if m: data['ONU Serial No'] = m.group(1)
    
    m = re.search(r'(?:ONT ID|Channel ID)\s*[:：]?\s*(\d+)', text)
    if m: data['ONT ID'] = int(m.group(1))

    m = re.search(r'(?:رقم\s*الدائرة|رقم\s*الدائره)\s*[:：]?\s*(\d+)', text)
    if m: data['Circuit Number'] = m.group(1)

    m = re.search(r'(?:المستخدم\s*النهائى|المستخدم\s*النهائي|العميل)\s*[:：]?\s*(.+)', text)
    if m: data['CST name'] = m.group(1).strip()

    m = re.search(r'(?:كود\s*الكابينة|كود\s*الكبينه|كود\s*Cabinet)\s*[:：]?\s*([\w\-]+)', text)
    if m: data['MSAN Code'] = m.group(1).strip()

    m = re.search(r'(?:Splitter|اسبليتر|الإسبليتر)\s*[:：]?\s*(.+)', text)
    if m: data['Splitter'] = m.group(1).strip()

    m = re.search(r'(?:OLT Name|اسم الـ OLT|OLT)\s*[:：]?\s*(.+)', text)
    if m: data['OLT Name'] = m.group(1).strip()

    # Speed extraction (GPON)
    m = re.search(r'السرع[ةه]\s*المطلوب[ةه]\s*[:：]?\s*\n?\s*([A-Za-z]*\s*\d+\s*[A-Za-z]*)', text, re.I)
    if m: data['Speed'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    m_port = re.search(r'رقم\s*البورت\s*[:：]?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)', text)
    if m_port:
        data['shelf'], data['card'], data['port'] = m_port.groups()
    
    return data

def parse_fiber_data(text: str) -> dict:
    """منطق استخراج البيانات لملفات Fiber."""
    data = {'Mode': 'Fiber', 'Circuit Number': None, 'Order Option': None, 'port': None, 
            'MSAN Code': None, 'Speed': None}

    m = re.search(r'Retail\s*Number\s*:\s*(.+)', text)
    if m: data['Circuit Number'] = m.group(1).strip()

    m = re.search(r'Order\s*Option\s*:\s*(.+)', text)
    if m: data['Order Option'] = m.group(1).strip().split(',')[-1].strip()

    m = re.search(r'Port\s*No\s*:\s*([\d\\]+)', text)
    if m: data['port'] = m.group(1).replace('\\', '/')

    m = re.search(r'Code\s*:\s*([\d\-\s]+)', text)
    if m: data['MSAN Code'] = re.sub(r'\s+', '', m.group(1)).strip()
    
    m = re.search(r'السرعة\s*المطلوب[ةه]\s*:\s*(\S+)', text, re.I)
    if m: data['Speed'] = m.group(1).strip()

    return data

# ------------------------------------------------------------------
# 3. التكامل والتشغيل (Integration & Runner)
# ------------------------------------------------------------------

def extract_from_pdf_to_dict(pdf_path: str, mode: str = "GPON") -> dict:
    """دالة الربط مع ECRM Extractor: تحويل البيانات لمسميات موحدة."""
    if not os.path.exists(pdf_path): return {}

    mode_upper = mode.upper()
    if "FIBER" in mode_upper:
        text = extract_text_fiber_style(pdf_path)
        raw_data = parse_fiber_data(text)
    else:
        text = extract_text_gpon_style(pdf_path)
        raw_data = parse_gpon_data(text)
    
    # استخدام محرك التوحيد الداخلي لضمان تطابق البيانات تماماً
    return _map_to_unified_format(raw_data, mode_upper)

def _map_to_unified_format(data: dict, mode: str) -> dict:
    """محرك داخلي لتوحيد مسميات الحقول وتنسيقها."""
    return {
        "Cabinet": data.get("MSAN Code"),
        "Splitter": data.get("Splitter"),
        "OLT Name": data.get("OLT Name"),
        "Slot": data.get("ONT ID") if data.get("ONT ID") is not None else data.get("Order Option"),
        "Port": str(data.get("port")) if "/" in str(data.get("port", "")) else f"{data.get('shelf')}/{data.get('card')}/{data.get('port')}" if data.get('shelf') is not None else data.get("port"),
        "ONU Serial Number": data.get("ONU Serial No"),
        "CST Name": data.get("CST name"),
        "Circuit Number": data.get("Circuit Number"),
        "Speed": data.get("Speed"),
        "Transmission Type": mode
    }

def run_wo_unified(input_root: str = DEFAULT_INPUT_ROOT, mode: str = None, log=print):
    """
    التشغيل الموحد: يمسح المجلدات (GPON, Fiber, Local Loop, WiMax) 
    ويستخرج البيانات في ملف إكسيل واحد.
    """
    if not os.path.exists(input_root):
        os.makedirs(input_root, exist_ok=True)
        for f in ["GPON", "Fiber", "Local Loop", "WiMax"]: os.makedirs(os.path.join(input_root, f), exist_ok=True)
        log(f"📁 Created input structure in '{input_root}'. Put PDFs in technology folders.")
        return

    all_results = []
    
    # إذا تم تمرير نمط معين (مثل GPON من الـ Launcher) نعالج مجلده فقط
    target_subfolders = [mode] if mode and mode in ["GPON", "Fiber", "Local Loop", "WiMax"] else ["GPON", "Fiber", "Local Loop", "WiMax"]

    for subfolder in target_subfolders:
        folder_path = os.path.join(input_root, subfolder)
        if not os.path.exists(folder_path): continue
        
        files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        if not files: continue
        
        log(f"🚀 Processing {len(files)} files in '{subfolder}'...")
        
        for filename in files:
            file_path = os.path.join(folder_path, filename)
            try:
                # اختيار المحرك والبارسر بناءً على اسم المجلد
                if subfolder == "Fiber":
                    text = extract_text_fiber_style(file_path)
                    raw_data = parse_fiber_data(text)
                else:
                    text = extract_text_gpon_style(file_path)
                    raw_data = parse_gpon_data(text)
                
                # توحيد البيانات قبل الإضافة للقائمة لضمان تطابق الإكسيل المستقل مع ECRM
                data = _map_to_unified_format(raw_data, subfolder)
                data['Filename'] = filename
                all_results.append(data)
            except Exception as e:
                log(f"❌ Error in {filename}: {e}")

    if not all_results:
        log("⚠️ No data extracted. Ensure PDFs are in the correct subfolders.")
        return

    # تصدير البيانات
    df = pd.DataFrame(all_results)
    
    # إعادة ترتيب الأعمدة بشكل احترافي
    cols = ['Transmission Type', 'Filename', 'Circuit Number', 'Cabinet', 'Splitter', 'OLT Name', 'Slot', 'Port', 'ONU Serial Number', 'CST Name', 'Speed']
    existing_cols = [c for c in cols if c in df.columns]
    df = df[existing_cols]

    os.makedirs(DEFAULT_OUTPUT_FOLDER, exist_ok=True)
    output_path = os.path.join(DEFAULT_OUTPUT_FOLDER, DEFAULT_OUTPUT_FILENAME)
    
    # الحفظ في شيتات متعددة داخل نفس ملف الإكسيل
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # الشيت الرئيسي للكل
        df.to_excel(writer, sheet_name='All Results', index=False)
        
        # شيت لكل نوع ربط
        if 'Transmission Type' in df.columns:
            for t_type, group in df.groupby('Transmission Type'):
                sheet_name = "".join(c for c in str(t_type) if c.isalnum() or c in " _-")[:31]
                group.to_excel(writer, sheet_name=sheet_name or "Other", index=False)
    
    log(f"✅ Finished! Saved {len(all_results)} records to: {output_path}")
    return all_results

def main():
    run_wo_unified()

if __name__ == '__main__':
    main()