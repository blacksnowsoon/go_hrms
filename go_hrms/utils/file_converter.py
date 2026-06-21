import io
import re
import frappe
import openpyxl
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from pypdf import PdfReader


# Arabic Unicode ranges (letters + diacritics + presentation forms)
_ARABIC_CHAR = r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\u064B-\u065F]'
_ARABIC_RUN = re.compile(rf'(?:{_ARABIC_CHAR} )+{_ARABIC_CHAR}')
_ARABIC_DETECT = re.compile(_ARABIC_CHAR)


def _fix_arabic_layout(text):
	"""
	layout mode in pypdf places each Arabic glyph at its visual x-position (left→right).
	Arabic reads right→left on the page, so the LAST letter in reading order sits furthest
	left, and appears FIRST in a left-to-right scan.  The result is a run of single chars
	separated by spaces in reversed logical order, e.g. "ن ا ض م ر ي" instead of "يرمضان".

	This function detects such runs (2+ single Arabic chars each separated by exactly one
	space) and reverses them to restore correct logical Unicode order.
	Correctly-formed Arabic words (no inter-char spaces) are left untouched.
	"""
	def _reverse_run(m):
		chars = re.findall(_ARABIC_CHAR, m.group(0))
		return ''.join(reversed(chars))

	return _ARABIC_RUN.sub(_reverse_run, text)


@frappe.whitelist(allow_guest=True)
def convert_pdf_to_excel():
	# Verify request method
	if frappe.request.method != "POST":
		frappe.local.response['http_status_code'] = 405
		return {"error": "Method Not Allowed"}

	try:
		# 1. File existence validation
		if "file" not in frappe.request.files:
			frappe.local.response['http_status_code'] = 400
			return {"error": "No file was uploaded."}

		file_obj = frappe.request.files["file"]
		filename = file_obj.filename

		# 2. File size validation (max 10MB)
		file_content = file_obj.read()
		max_size = 10 * 1024 * 1024
		if len(file_content) > max_size:
			frappe.local.response['http_status_code'] = 400
			return {"error": "File size exceeds the 10MB limit."}

		# 3. File content validation (PDF magic bytes)
		# TODO(security): Validate file header signature
		if not file_content.startswith(b"%PDF"):
			frappe.local.response['http_status_code'] = 400
			return {"error": "Invalid file format. Please upload a valid PDF file."}

		# 4. Parse PDF
		try:
			pdf_file = io.BytesIO(file_content)
			reader = PdfReader(pdf_file)
		except Exception as e:
			frappe.local.response['http_status_code'] = 400
			return {"error": f"Failed to parse PDF: {str(e)}"}

		# 5. Extract text and validate OCR requirements (plain mode for quick check)
		extracted_text = ""
		for page in reader.pages:
			extracted_text += page.extract_text() or ""

		cleaned_text = extracted_text.strip()
		frappe.errprint(f"extracted text : {cleaned_text}")
		if len(cleaned_text) < 10:
			frappe.local.response['http_status_code'] = 400
			return {"error": "The PDF appears to be scanned or contains no extractable text. Scanned PDFs requiring OCR are not supported."}

		# 6. Generate Excel workbook
		wb = openpyxl.Workbook()
		ws = wb.active
		ws.title = "PDF Content"

		has_arabic = bool(_ARABIC_DETECT.search(cleaned_text))

		row_num = 1
		default_font = Font(name="Calibri", size=11)

		for page in reader.pages:
			# Use layout mode to preserve inter-column spacing.
			# Arabic glyph ordering is fixed by _fix_arabic_layout() below.
			page_text = page.extract_text(extraction_mode="layout") or ""
			lines = page_text.splitlines()

			for line in lines:
				stripped_line = line.strip()
				if not stripped_line:
					continue  # skip layout-mode blank lines; don't add empty Excel rows

				# Split into columns using 2+ spaces (layout mode preserves visual spacing)
				parts = re.split(r' {2,}', stripped_line)

				# Filter empty parts, then fix any split Arabic character runs
				parts = [_fix_arabic_layout(p).strip() for p in parts if p.strip()]
				if not parts:
					continue

				for col_idx, val in enumerate(parts, 1):
					cell = ws.cell(row=row_num, column=col_idx, value=val)
					cell.font = default_font
					cell.alignment = Alignment(horizontal="left", vertical="center")

				row_num += 1

		# 7. Auto-fit column widths (max-length calculation)
		for col in ws.columns:
			max_len = 0
			col_letter = get_column_letter(col[0].column)
			for cell in col:
				val = str(cell.value or '')
				if len(val) > max_len:
					max_len = len(val)
			# Add padding and apply min/max constraints
			ws.column_dimensions[col_letter].width = min(max(max_len + 3, 10), 50)

		# 8. Save output and return binary
		output = io.BytesIO()
		wb.save(output)
		output.seek(0)
		excel_bytes = output.read()

		# Prepare response
		frappe.response['type'] = 'binary'

		# Build a safe ASCII-only filename.
		# Frappe's as_binary handler does .encode("utf-8").decode("unicode-escape")
		# on the filename, which corrupts any non-ASCII characters (e.g. Arabic).
		# Stripping to ASCII avoids garbled symbols like "Ø¹ÙØ±..."
		base_name = filename.rsplit('.', 1)[0] if filename else "converted"
		ascii_name = ''.join(c for c in base_name if ord(c) < 128)
		ascii_name = re.sub(r'[^\w\s\.-]', '_', ascii_name)  # remove non-word chars
		ascii_name = re.sub(r'\s+', '_', ascii_name).strip('_')  # spaces → underscores
		if not ascii_name:
			ascii_name = "converted"
		frappe.response['filename'] = f"{ascii_name}.xlsx"
		frappe.response['filecontent'] = excel_bytes

	except Exception as e:
		frappe.local.response['http_status_code'] = 500
		return {"error": f"An unexpected error occurred during conversion: {str(e)}"}

