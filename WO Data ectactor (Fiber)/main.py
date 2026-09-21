import os
import re
import unicodedata
import pandas as pd
from PyPDF2 import PdfReader

# ==========================
# Default paths
# ==========================

DEFAULT_INPUT_FOLDER = "WOs"
DEFAULT_OUTPUT_FOLDER = "Output"
DEFAULT_OUTPUT_FILE = os.path.join(DEFAULT_OUTPUT_FOLDER, "all_extracted_data.xlsx")


# ==========================
# PDF Text Extraction
# ==========================

def extract_text_from_pdf(file_path):
    """
    Extracts and cleans text from a PDF file.
    """

    try:
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            extracted = page.extract_text()

            if extracted:
                text += extracted + "\n"

        # Remove invisible unicode chars
        text = re.sub(r'[\u200f\u200e\u200b\u00a0\r]+', ' ', text)

        # Normalize Arabic
        text = unicodedata.normalize("NFKC", text)

        return text

    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""


# ==========================
# Parse Data
# ==========================

def parse_pdf_data(text):

    # ---------------- CID ----------------

    cid_match = re.search(
        r"Retail\s*Number\s*:\s*(.+)",
        text,
        re.IGNORECASE
    )

    cid = cid_match.group(1).strip() if cid_match else ""

    # ---------------- Order Number ----------------

    order_number = ""

    order_number_match = re.search(
        r"رقم\s*الطلب\s*:\s*([^\s]+)",
        text,
        re.IGNORECASE
    )

    if order_number_match:
        order_number = order_number_match.group(1).strip()

    # ---------------- Order Option ----------------

    order_option = ""

    order_match = re.search(
        r"Order\s*Option\s*:\s*(.+)",
        text,
        re.IGNORECASE
    )

    if order_match:
        parts = order_match.group(1).strip().split(",")

        order_option = parts[-1].strip()

    # ---------------- Port ----------------

    port = ""

    port_match = re.search(
        r"Port\s*No\s*:\s*([0-9\\/\s]+)",
        text,
        re.IGNORECASE
    )

    if port_match:
        port = re.sub(r"\s+", "", port_match.group(1))
        port = port.replace("\\", "/")

    # ---------------- Cabinet Code ----------------

    cabinet_code = ""

    cabinet_match = re.search(
        r"Code\s*:\s*([\d\-\s]+)",
        text,
        re.IGNORECASE
    )

    if cabinet_match:
        cabinet_code = re.sub(
            r"\s+",
            "",
            cabinet_match.group(1)
        )

    if not cabinet_code:

        switch_match = re.search(
            r"Switch\s*:\s*([\d\-]+)",
            text,
            re.IGNORECASE
        )

        if switch_match:
            cabinet_code = switch_match.group(1)

    # ---------------- Speed ----------------

    speed = ""

    speed_match = re.search(
        r"السرعة\s*المطلوب[ةه]\s*:\s*(\S+)",
        text,
        re.IGNORECASE
    )

    if speed_match:
        speed = speed_match.group(1).strip()

    return {
        "Filename": "",
        "Order Number": order_number,
        "CID": cid,
        "Order Option": order_option,
        "Port": port,
        "Cabinet Code": cabinet_code,
        "Speed": speed
    }


def sanitize_name_part(value):
    """Convert a field into a safe file-name fragment."""

    if value is None:
        return ""

    text = str(value).strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[^\w.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._")

    return text


def build_pdf_name(data):
    """Build a renamed PDF filename using CID_Port_OrderOption format."""

    cid = sanitize_name_part(data.get("CID", ""))
    port = sanitize_name_part(data.get("Port", ""))
    order_option = sanitize_name_part(data.get("Order Option", ""))

    parts = [part for part in [cid, port, order_option] if part]

    if not parts:
        return ""

    return f"{'_'.join(parts)}.pdf"


def resolve_output_path(folder_path, filename):
    """Resolve the destination path for a processed PDF in the output folder."""

    output_folder = DEFAULT_OUTPUT_FOLDER
    os.makedirs(output_folder, exist_ok=True)
    return os.path.join(output_folder, filename)


# ==========================
# Main Extractor
# ==========================

def run_fiber_extractor(
    folder_path=DEFAULT_INPUT_FOLDER,
    output_file=DEFAULT_OUTPUT_FILE,
    log=print
):

    all_data = []

    if not os.path.exists(folder_path):
        log(f"Folder '{folder_path}' not found!")
        return

    files = [
        f for f in os.listdir(folder_path)
        if f.lower().endswith(".pdf")
    ]

    log(f"Found {len(files)} PDF file(s)\n")

    for filename in files:

        filepath = os.path.join(folder_path, filename)

        try:

            text = extract_text_from_pdf(filepath)

            data = parse_pdf_data(text)

            new_name = build_pdf_name(data)

            if new_name:
                new_filepath = resolve_output_path(folder_path, new_name)

                if os.path.abspath(new_filepath) != os.path.abspath(filepath):
                    candidate = new_filepath
                    counter = 1

                    while os.path.exists(candidate) and os.path.abspath(candidate) != os.path.abspath(filepath):
                        stem, ext = os.path.splitext(new_name)
                        candidate = os.path.join(os.path.dirname(new_filepath), f"{stem}_{counter}{ext}")
                        counter += 1

                    os.replace(filepath, candidate)
                    filepath = candidate

            data["Filename"] = os.path.basename(filepath)

            all_data.append(data)

            log(f"Processed: {filename} -> {data['Filename']}")

        except Exception as e:

            log(f"Error in {filename}: {e}")

    if not all_data:

        log("No data extracted.")

        return

    df = pd.DataFrame(all_data)

    # ترتيب الأعمدة
    columns = [
        "Filename",
        "Order Number",
        "CID",
        "Order Option",
        "Port",
        "Cabinet Code",
        "Speed"
    ]

    df = df[columns]

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    df.to_excel(output_file, index=False)

    log("")
    log("=" * 50)
    log(f"Successfully extracted {len(df)} PDF(s)")
    log(f"Saved to : {output_file}")
    log("=" * 50)


# ==========================
# Main
# ==========================

def main():
    run_fiber_extractor()


if __name__ == "__main__":
    main()