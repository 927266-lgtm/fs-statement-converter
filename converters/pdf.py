import os
import re
import pdfplumber

# Try importing easyocr for scanned pages
try:
    import easyocr
    import numpy as np
    from PIL import Image
    _EASYOCR_AVAILABLE = True
except ImportError:
    _EASYOCR_AVAILABLE = False

_READER_CACHE = {}

def get_ocr_reader(lang='en'):
    global _READER_CACHE
    if lang not in _READER_CACHE:
        print(f"  → Initializing EasyOCR reader for lang: {lang} (this might take a few seconds)...")
        # easyocr automatically checks for GPU availability. verbose=False avoids console print encoding errors.
        _READER_CACHE[lang] = easyocr.Reader([lang], verbose=False)
    return _READER_CACHE[lang]

def parse_financial_number(val_str: str):
    """
    Parses financial number strings into float values.
    Handles parenthetical negatives like (1,200), dollar signs, commas, and dashes for zero.
    Examples:
      "$ (1,200.50)" -> -1200.50
      "(150)" -> -150.0
      "-" -> 0.0
      "1,500,000" -> 1500000.0
    """
    if not val_str:
        return None
    
    s = val_str.strip()
    
    # Check for empty-like values
    if s == "-" or s == "—" or s == "–":
        return 0.0
    
    # Remove currency symbols and spaces
    s = s.replace("$", "").replace("€", "").replace("£", "").strip()
    
    # Check for parenthetical negative: (1,200.50) -> -1200.50
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
        
    # Remove commas
    s = s.replace(",", "")
    
    # Check if it is a number
    try:
        val = float(s)
        return -val if is_negative else val
    except ValueError:
        return None


def extract_grid_text(page, char_width_est=5.5, line_tolerance=3.5) -> str:
    """
    Custom text extraction algorithm to preserve columns/grids in financial statements.
    Groups words by top-coordinate, sorts them horizontally, and spaces them out.
    """
    words = page.extract_words()
    if not words:
        return ""
        
    # Sort words by top position, then left position
    words_sorted = sorted(words, key=lambda w: (w["top"], w["x0"]))
    
    # Group words into lines
    lines = []
    current_line = []
    current_top = -1
    
    for w in words_sorted:
        if current_top == -1:
            current_top = w["top"]
            current_line.append(w)
        elif abs(w["top"] - current_top) <= line_tolerance:
            current_line.append(w)
        else:
            lines.append(current_line)
            current_line = [w]
            current_top = w["top"]
            
    if current_line:
        lines.append(current_line)
        
    # Reconstruct text line by line with spaces
    output_lines = []
    for line in lines:
        line_sorted = sorted(line, key=lambda w: w["x0"])
        line_str = []
        last_x1 = 0.0
        
        for w in line_sorted:
            spacing = w["x0"] - last_x1
            if last_x1 > 0:
                spaces_count = int(round(spacing / char_width_est))
                # Ensure spacing is realistic
                if spacing < 1.5:
                    spaces_count = 0
                elif spaces_count < 1:
                    spaces_count = 1
                line_str.append(" " * spaces_count)
            else:
                # Leading indentation
                leading_spaces = int(round(w["x0"] / char_width_est))
                line_str.append(" " * leading_spaces)
                
            line_str.append(w["text"])
            last_x1 = w["x1"]
            
        output_lines.append("".join(line_str))
        
    return "\n".join(output_lines)


def format_table_as_markdown(table) -> str:
    """Formats a list-of-lists table as a markdown table for LLM readability."""
    if not table or not any(table):
        return ""
        
    # Clean rows: fill None values
    clean_table = []
    for row in table:
        clean_row = [str(cell).strip() if cell is not None else "" for cell in row]
        clean_table.append(clean_row)
        
    # Determine max column widths
    col_widths = [0] * len(clean_table[0])
    for row in clean_table:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
                
    markdown_lines = []
    # Header row
    hdr = clean_table[0]
    hdr_line = "| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(hdr)) + " |"
    markdown_lines.append(hdr_line)
    
    # Separator row
    sep_line = "| " + " | ".join("-" * col_widths[i] for i in range(len(col_widths))) + " |"
    markdown_lines.append(sep_line)
    
    # Data rows
    for row in clean_table[1:]:
        row_line = "| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(row)) + " |"
        markdown_lines.append(row_line)
        
    return "\n".join(markdown_lines)


def extract_pdf(file_path: str) -> dict:
    """
    Extracts text and table information from a financial statement PDF.
    Returns a dictionary of raw page data.
    """
    raw_doc = {
        "filename": os.path.basename(file_path),
        "pages": [],
        "total_pages": 0,
        "ocr_needed_pages": 0
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            raw_doc["total_pages"] = len(pdf.pages)
            
            for idx, page in enumerate(pdf.pages):
                page_num = idx + 1
                
                # Extract words using custom layout logic
                grid_text = extract_grid_text(page)
                standard_text = page.extract_text() or ""
                
                # Extract tables using pdfplumber's heuristics
                tables = []
                extracted = page.extract_tables()
                if extracted:
                    for t in extracted:
                        # Convert table elements to clean rows
                        if t and any(t):
                            tables.append(t)
                            
                # Determine quality/need for OCR (Scanned pages have visual content but no selectable text)
                text_len = len(standard_text.strip())
                
                # Calculate what percentage of the page is covered by images
                page_area = float(page.width) * float(page.height)
                img_area_ratio = 0.0
                if page_area > 0 and page.images:
                    total_img_area = sum(float(img.get("width", 0)) * float(img.get("height", 0)) for img in page.images)
                    img_area_ratio = total_img_area / page_area
                
                # Check if the page is completely blank (no text and no visual elements)
                is_blank = (
                    len(page.images) == 0 and 
                    len(page.rects) == 0 and 
                    len(page.lines) == 0 and 
                    len(page.curves) == 0 and
                    text_len == 0
                )
                
                # A page is scanned if it has visual objects but absolutely zero text, 
                # OR if it has sparse text (< 150 chars) but has large images covering > 50% of the page (typical for scanned sheets)
                is_scanned = (text_len == 0 and not is_blank) or (text_len < 150 and img_area_ratio > 0.5)
                
                ocr_performed = False
                ocr_text = ""
                
                if is_scanned:
                    raw_doc["ocr_needed_pages"] += 1
                    
                    if _EASYOCR_AVAILABLE:
                        print(f"  → Running EasyOCR on scanned page {page_num}...")
                        try:
                            # Render page to PIL image
                            img_obj = page.to_image(resolution=150).original
                            
                            # Run EasyOCR
                            reader = get_ocr_reader('en')
                            img_np = np.array(img_obj)
                            results = reader.readtext(img_np, detail=0)
                            ocr_text = "\n".join(results)
                            
                            if ocr_text.strip():
                                grid_text = ocr_text
                                standard_text = ocr_text
                                ocr_performed = True
                                # Reset is_scanned flag since we successfully parsed it
                                is_scanned = False
                                # Decrement needed pages count
                                raw_doc["ocr_needed_pages"] = max(0, raw_doc["ocr_needed_pages"] - 1)
                                print(f"    ✓ Page {page_num} OCR complete: {len(ocr_text)} characters extracted.")
                            else:
                                print(f"    ⚠ Page {page_num} OCR returned no text.")
                        except Exception as ocr_err:
                            print(f"    ✗ OCR failed on page {page_num}: {ocr_err}")
                    else:
                        print(f"  ⚠ Page {page_num} is scanned but easyocr is not installed.")
                    
                # Format extracted tables as markdown to append to text for LLM use
                md_tables_text = ""
                if tables:
                    md_tables_text = "\n\n### Extracted Tabular Data (Standardized):\n"
                    for t_idx, t in enumerate(tables):
                        md_tables_text += f"\nTable {t_idx+1}:\n" + format_table_as_markdown(t) + "\n"
                
                raw_doc["pages"].append({
                    "page_number": page_num,
                    "text": grid_text + md_tables_text,
                    "raw_text": standard_text,
                    "tables": tables,
                    "is_scanned": is_scanned,
                    "ocr_performed": ocr_performed
                })
                
    except Exception as e:
        raw_doc["error"] = f"Failed to parse PDF: {str(e)}"
        
    return raw_doc
