import os
from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph

def iter_block_items(parent):
    """
    Yields each paragraph and table in the order they appear in the Word document.
    """
    if isinstance(parent, DocxDocument):
        parent_elm = parent.element.body
    else:
        parent_elm = parent
        
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield DocxParagraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield DocxTable(child, parent)


def format_docx_table_as_markdown(table) -> str:
    """Extracts a python-docx table as a list of lists and formats as markdown."""
    rows = []
    for r in table.rows:
        row_cells = [cell.text.strip() for cell in r.cells]
        rows.append(row_cells)
        
    if not rows:
        return ""
        
    # Standardize table (remove consecutive duplicates due to merged cells)
    clean_table = []
    for r in rows:
        # Merged cells in Word can lead to identical text in adjacent cells.
        # We preserve them as is, but fill empty/None cells.
        clean_row = [c if c is not None else "" for c in r]
        clean_table.append(clean_row)
        
    # Format markdown
    col_widths = [0] * len(clean_table[0])
    for r in clean_table:
        for i, cell in enumerate(r):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(cell))
                
    lines = []
    # Header
    hdr = clean_table[0]
    lines.append("| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(hdr)) + " |")
    # Separator
    lines.append("| " + " | ".join("-" * col_widths[i] for i in range(len(col_widths))) + " |")
    # Rows
    for r in clean_table[1:]:
        lines.append("| " + " | ".join(cell.ljust(col_widths[i]) for i, cell in enumerate(r)) + " |")
        
    return "\n".join(lines), clean_table


def extract_word(file_path: str) -> dict:
    """
    Extracts text and table information from a financial statement Word file (.docx).
    """
    raw_doc = {
        "filename": os.path.basename(file_path),
        "pages": [],
        "total_pages": 1,
        "ocr_needed_pages": 0
    }
    
    try:
        doc = Document(file_path)
        
        full_elements_text = []
        tables_data = []
        
        for block in iter_block_items(doc):
            if isinstance(block, DocxParagraph):
                p_text = block.text.strip()
                if p_text:
                    full_elements_text.append(p_text)
            elif isinstance(block, DocxTable):
                md_tbl, raw_tbl = format_docx_table_as_markdown(block)
                if md_tbl:
                    full_elements_text.append(md_tbl)
                    tables_data.append(raw_tbl)
                    
        full_text = "\n\n".join(full_elements_text)
        
        # Word has a single fluid flow, we treat it as 1 main 'page' for the chunker
        raw_doc["pages"].append({
            "page_number": 1,
            "text": full_text,
            "raw_text": full_text,
            "tables": tables_data,
            "is_scanned": False
        })
        
    except Exception as e:
        raw_doc["error"] = f"Failed to parse Word Document: {str(e)}"
        
    return raw_doc
