import os
import re
import fitz  # PyMuPDF
import pandas as pd
import os

DEFAULT_INPUT_FOLDER = 'WOs'
DEFAULT_OUTPUT_FOLDER = 'WOs output'
DEFAULT_OUTPUT_FILENAME = 'extracted_data.xlsx'


def extract_text_from_pdf(file_path: str) -> str:
    try:
        doc = fitz.open(file_path)
        text_parts = []

        for page in doc:
            # First try fast plain-text extraction
            try:
                extracted = page.get_text('text')
                if extracted:
                    text_parts.append(extracted)
                continue
            except Exception:
                pass

            # Fallback to rawdict parsing
            try:
                raw = page.get_text('rawdict') or {}
                for block in raw.get('blocks') or []:
                    for line in block.get('lines') or []:
                        for span in line.get('spans') or []:
                            t = span.get('text')
                            if t:
                                text_parts.append(t)
                                text_parts.append(' ')
            except Exception:
                continue

        text = ''.join(text_parts)
        return text.replace('\u200f', '').replace('\u200e', '')
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ''


def extract_data(text: str) -> dict:
    data = {
        'Circuit Number': None,
        'shelf': None,
        'card': None,
        'port': None,
        'ONT ID': None,
        'ONU Serial No': None,
        'CST name': None,
        'MSAN Code': None,
        'Splitter': None,
        'OLT Name': None,
        'Speed': None,
    }

    match_onu = re.search(r'ONU Serial No\s*[:：]?\s*([A-Fa-f0-9]+)', text)
    if match_onu:
        data['ONU Serial No'] = match_onu.group(1)

    match_ont_id = re.search(r'(?:ONT ID|Channel ID)\s*[:：]?\s*(\d+)', text)
    if match_ont_id:
        data['ONT ID'] = int(match_ont_id.group(1))

    match_circuit = re.search(r'(?:رقم\s*الدائرة|رقم\s*الدائره)\s*[:：]?\s*(\d+)', text)
    if match_circuit:
        data['Circuit Number'] = match_circuit.group(1)

    match_cst = re.search(r'(?:المستخدم\s*النهائى|المستخدم\s*النهائي|العميل)\s*[:：]?\s*(.+)', text)
    if match_cst:
        data['CST name'] = match_cst.group(1).strip()

    match_msan = re.search(
        r'(?:كود\s*الكابينة|كود\s*الكبينه|كود\s*Cabinet)\s*[:：]?\s*([\w\-]+)',
        text,
    )
    if match_msan:
        data['MSAN Code'] = match_msan.group(1).strip()

    # استخراج الاسبليتر والـ OLT للربط مع ECRM
    match_splitter = re.search(r'(?:Splitter|اسبليتر|الإسبليتر)\s*[:：]?\s*(.+)', text)
    if match_splitter:
        data['Splitter'] = match_splitter.group(1).strip()

    match_olt = re.search(r'(?:OLT Name|اسم الـ OLT|OLT)\s*[:：]?\s*(.+)', text)
    if match_olt:
        data['OLT Name'] = match_olt.group(1).strip()

    # Speed extraction
    match_speed = re.search(
        r'السرع[ةه]\s*المطلوب[ةه]\s*[:：]?\s*\n?\s*([A-Za-z]*\s*\d+\s*[A-Za-z]*)',
        text,
        re.IGNORECASE,
    )
    if match_speed:
        speed = match_speed.group(1)
        speed = re.sub(r'\s+', ' ', speed).strip()

        if re.match(r'^M\d+', speed, re.IGNORECASE):
            speed = speed.upper()
        elif re.match(r'^\d+\s*Kbps', speed, re.IGNORECASE):
            speed = speed.replace('kbps', 'Kbps')
        elif re.match(r'^\d+$', speed):
            speed = f"{speed} Kbps"

        data['Speed'] = speed

    if not data['Speed']:
        match_kbps_rev = re.search(r'Kbps\s*(\d+)', text, re.IGNORECASE)
        if match_kbps_rev:
            data['Speed'] = f"{match_kbps_rev.group(1)} Kbps"

    if not data['Speed']:
        lines = text.split('\n')
        for line in lines:
            if 'سرع' in line or 'Kbps' in line or 'Mbps' in line:
                match_any = re.search(r'(\d+)\s*(Kbps|Mbps)?', line, re.IGNORECASE)
                if match_any:
                    val = match_any.group(1)
                    unit = match_any.group(2) if match_any.group(2) else 'Kbps'
                    data['Speed'] = f"{val} {unit}"
                    break

    match_port = re.search(
        r'رقم\s*البورت\s*[:：]?\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)',
        text,
    )
    if match_port:
        data['shelf'] = int(match_port.group(1))
        data['card'] = int(match_port.group(2))
        data['port'] = int(match_port.group(3))
    else:
        reversed_text = text[::-1]
        match_port_rev = re.search(
            r'(\d+)\s*/\s*(\d+)\s*/\s*(\d+)\s*[:：]?\s*ترﻮﺒﻟا',
            reversed_text,
        )
        if match_port_rev:
            data['shelf'] = int(match_port_rev.group(3))
            data['card'] = int(match_port_rev.group(2))
            data['port'] = int(match_port_rev.group(1))

    return data


def extract_from_pdf_to_dict(pdf_path: str, mode: str = "GPON") -> dict:
    """
    دالة الربط مع ECRM Extractor: تستقبل مسار ملف واحد وترجع البيانات كقاموس.
    """
    if not os.path.exists(pdf_path):
        return {}

    text = extract_text_from_pdf(pdf_path)
    data = extract_data(text)
    
    # تحويل البيانات للمسميات التي يتوقعها ملف runner.py في ECRM
    return {
        "Cabinet": data.get("MSAN Code"),
        "Splitter": data.get("Splitter"),
        "OLT Name": data.get("OLT Name"),
        "Slot": data.get("ONT ID"),
        "Port": f"{data.get('shelf')}/{data.get('card')}/{data.get('port')}" if data.get('port') else None,
        "ONU Serial Number": data.get("ONU Serial No"),
        "CST Name": data.get("CST name")
    }


def run_gpon_wo(input_folder: str = DEFAULT_INPUT_FOLDER, pdf_path: str = None, output_file: str | None = None, log=print):
    """
    تشغيل المحرك: يدعم معالجة مجلد كامل أو ملف واحد فقط.
    """
    # حالة معالجة ملف واحد (استدعاء من ECRM)
    if pdf_path:
        if not os.path.exists(pdf_path):
            log(f"❌ File not found: {pdf_path}")
            return {}
        text = extract_text_from_pdf(pdf_path)
        return extract_data(text)

    # حالة معالجة مجلد (Standalone)
    if not os.path.exists(input_folder):
        log(f"❌ Input folder '{input_folder}' does not exist.")
        return

    results = []
    
    # التأكد من وجود المجلد
    if not os.path.exists(input_folder):
        os.makedirs(input_folder, exist_ok=True)
        log(f"Created folder: {input_folder}. Put your PDFs there.")
        return

    for filename in os.listdir(input_folder):
        if not filename.lower().endswith('.pdf'):
            continue

        file_path = os.path.join(input_folder, filename)
        log(f"Processing file: {filename}")

        text = extract_text_from_pdf(file_path)
        extracted = extract_data(text)
        extracted['CID'] = filename
        results.append(extracted)

    if not results:
        log("\n⚠️ No PDF data was extracted.")
        return

    df = pd.DataFrame(
        results,
        columns=[
            'CID',
            'Circuit Number',
            'shelf',
            'card',
            'port',
            'ONT ID',
            'ONU Serial No',
            'CST name',
            'MSAN Code',
            'Speed',
        ],
    )

    if output_file is None:
        os.makedirs(DEFAULT_OUTPUT_FOLDER, exist_ok=True)
        output_file = os.path.join(DEFAULT_OUTPUT_FOLDER, DEFAULT_OUTPUT_FILENAME)
    else:
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    df.to_excel(output_file, index=False)
    log(f"\n--- Data extracted and saved to: {output_file} ---")
    log(df)


def main():
    run_gpon_wo()


if __name__ == '__main__':
    main()
