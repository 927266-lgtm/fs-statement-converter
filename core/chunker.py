import re
import os
from converters.pdf import parse_financial_number

# Regex patterns for page-level classification (in order of priority check)
SECTION_PATTERNS = [
    ("UG_REPORT", re.compile(r"REPORT\s+ON\s+COMPLIANCE\s+FOR\s+EACH\s+MAJOR\s+PROGRAM|COMPLIANCE\s+REQUIRED\s+BY\s+THE\s+UNIFORM\s+GUIDANCE", re.IGNORECASE)),
    ("YB_REPORT", re.compile(r"REPORT\s+ON\s+INTERNAL\s+CONTROL\s+OVER\s+FINANCIAL\s+REPORTING|PERFORMED\s+IN\s+ACCORDANCE\s+WITH\s+GOVERNMENT\s+AUDITING\s+STANDARDS", re.IGNORECASE)),
    ("NOTES_SEFA", re.compile(r"NOTES\s+TO\s+(?:THE\s+)?SCHEDULE\s+OF\s+EXPENDITURES\s+OF\s+FEDERAL\s+AWARDS|NOTES\s+TO\s+(?:THE\s+)?SEFA", re.IGNORECASE)),
    ("SEFA", re.compile(r"SCHEDULE\s+OF\s+EXPENDITURES\s+OF\s+FEDERAL\s+AWARDS|\bSEFA\b", re.IGNORECASE)),
    ("FINDINGS", re.compile(r"SCHEDULE\s+OF\s+FINDINGS\s+AND\s+QUESTIONED\s+COSTS", re.IGNORECASE)),
    ("ACTION_PLAN", re.compile(r"CORRECTIVE\s+ACTION\s+PLAN|ACTION\s+PLAN\s+FOR\s+AUDIT\s+FINDINGS", re.IGNORECASE)),
    ("NOTES_FS", re.compile(r"NOTES\s+TO\s+(?:CONSOLIDATED\s+)?FINANCIAL\s+STATEMENTS", re.IGNORECASE)),
    ("CASH_FLOW", re.compile(r"STATEMENT\s+OF\s+CASH\s+FLOWS", re.IGNORECASE)),
    ("INCOME_STATEMENT", re.compile(r"STATEMENT\s+OF\s+ACTIVITIES|INCOME\s+STATEMENT|STATEMENT\s+OF\s+REVENUES\s*,\s*EXPENSES|STATEMENT\s+OF\s+OPERATIONS", re.IGNORECASE)),
    ("BALANCE_SHEET", re.compile(r"STATEMENT\s+OF\s+NET\s+POSITION|BALANCE\s+SHEET|STATEMENT\s+OF\s+FINANCIAL\s+POSITION", re.IGNORECASE)),
    ("AUDIT_REPORT", re.compile(r"INDEPENDENT\s+AUDITOR'S\s+REPORT|INDEPENDENT\s+AUDITOR’S\s+REPORT", re.IGNORECASE)),
    ("TOC", re.compile(r"TABLE\s+OF\s+CONTENTS|\bTOC\b|\bCONTENTS\b", re.IGNORECASE)),
]

# Sub-chunk splitter for Independent Auditor's Report
AUDIT_SUB_PATTERNS = [
    ("Opinion", re.compile(r"^\s*(?:Opinion|OPINION)\b", re.MULTILINE)),
    ("Basis for Opinion", re.compile(r"^\s*(?:Basis\s+for\s+Opinion|BASIS\s+FOR\s+OPINION)\b", re.MULTILINE)),
    ("Responsibilities of Management", re.compile(r"^\s*(?:Responsibilities\s+of\s+Management|Management’s\s+Responsibility|Management's\s+Responsibility|RESPONSIBILITIES\s+OF\s+MANAGEMENT)\b", re.MULTILINE)),
    ("Auditor's Responsibilities", re.compile(r"^\s*(?:Auditor(?:’s|'s)\s+Responsibilities|AUDITOR(?:’S|'S)\s+RESPONSIBILITIES)\b", re.MULTILINE)),
    ("Supplementary Information", re.compile(r"^\s*(?:Supplementary\s+Information|SUPPLEMENTARY\s+INFORMATION)\b", re.MULTILINE)),
    ("Other Reporting Required by Government Auditing Standards", re.compile(r"^\s*(?:Other\s+Reporting\s+Required\s+by\s+Government\s+Auditing\s+Standards|OTHER\s+REPORTING\s+REQUIRED\s+BY\s+GOVERNMENT\s+AUDITING\s+STANDARDS)\b", re.MULTILINE)),
]

# Regex to find Note headings: e.g. "Note 1 - Summary of..." or "Note 2. Cash and..." or "NOTE 1:" or "1. SUMMARY OF..."
NOTE_HEADER_REGEX = re.compile(
    r"^\s*(?:Note|NOTE)\s+(\d+)\b|^\s*(\d+)\.\s+([A-Z\s,\-]{6,50})$", 
    re.MULTILINE
)


def perform_balance_sheet_check(text: str) -> dict:
    """
    Performs audit math checks on the Balance Sheet text.
    Looks for Assets, Liabilities, and Net Assets / Equity values and verifies:
    Assets = Liabilities + Equity
    """
    results = {
        "assets": None,
        "liabilities": None,
        "net_assets": None,
        "liab_and_net_assets": None,
        "balanced": None,
        "message": "Values not found"
    }
    
    # Clean text to process line by line
    lines = text.split("\n")
    
    # Try to find values using regex
    # Target lines: "Total Assets", "Total Liabilities", "Total Net Assets", "Net Assets", "Total Liabilities and Net Assets"
    assets_re = re.compile(r"(?:Total\s+Assets)\s+([\d,()$\-\s—]+)$", re.IGNORECASE)
    liab_re = re.compile(r"(?:Total\s+Liabilities)\s+([\d,()$\-\s—]+)$", re.IGNORECASE)
    net_assets_re = re.compile(r"(?:Total\s+Net\s+Assets|Total\s+Equity|Net\s+Assets)\s+([\d,()$\-\s—]+)$", re.IGNORECASE)
    liab_net_assets_re = re.compile(r"(?:Total\s+Liabilities\s+and\s+Net\s+Assets|Total\s+Liabilities\s+and\s+Equity)\s+([\d,()$\-\s—]+)$", re.IGNORECASE)
    
    for line in lines:
        line_clean = line.strip()
        # Find match at end of lines
        m_assets = assets_re.search(line_clean)
        m_liab = liab_re.search(line_clean)
        m_net = net_assets_re.search(line_clean)
        m_tot = liab_net_assets_re.search(line_clean)
        
        if m_assets:
            val = parse_financial_number(m_assets.group(1))
            if val is not None:
                results["assets"] = val
        if m_liab:
            val = parse_financial_number(m_liab.group(1))
            if val is not None:
                results["liabilities"] = val
        if m_net:
            val = parse_financial_number(m_net.group(1))
            if val is not None:
                results["net_assets"] = val
        if m_tot:
            val = parse_financial_number(m_tot.group(1))
            if val is not None:
                results["liab_and_net_assets"] = val
                
    # Evaluate equation
    a = results["assets"]
    l = results["liabilities"]
    n = results["net_assets"]
    l_n = results["liab_and_net_assets"]
    
    if a is not None and l is not None and n is not None:
        calc_total = l + n
        diff = abs(a - calc_total)
        # Allow small rounding tolerance of $2
        if diff <= 2.0:
            results["balanced"] = True
            results["message"] = f"Balanced! Assets ({a:,.2f}) = Liabilities ({l:,.2f}) + Net Assets ({n:,.2f})"
        else:
            results["balanced"] = False
            results["message"] = f"Mismatched! Assets = {a:,.2f}, Liab + Net Assets = {calc_total:,.2f} (Diff: {diff:,.2f})"
    elif a is not None and l_n is not None:
        diff = abs(a - l_n)
        if diff <= 2.0:
            results["balanced"] = True
            results["message"] = f"Balanced! Assets ({a:,.2f}) equals Liabilities and Net Assets ({l_n:,.2f})"
        else:
            results["balanced"] = False
            results["message"] = f"Mismatched! Assets = {a:,.2f}, Liabilities and Net Assets = {l_n:,.2f} (Diff: {diff:,.2f})"
            
    return results


def chunk_document(raw_doc: dict, file_path: str) -> tuple:
    """
    Groups raw pages into logical financial audit sections and splits them into chunks.
    Returns: (chunks_list, registry_dict)
    """
    doc_stem = os.path.basename(file_path).rsplit(".", 1)[0]
    
    # 1. Classify each page
    page_sections = []
    current_section = "COVER"
    
    for idx, page in enumerate(raw_doc["pages"]):
        page_text = page["text"]
        matched_section = None
        
        # Check against patterns
        for sect_name, pattern in SECTION_PATTERNS:
            if pattern.search(page_text):
                matched_section = sect_name
                break
                
        if matched_section:
            current_section = matched_section
        elif idx == 0:
            current_section = "COVER"
            
        page_sections.append((page, current_section))
        
    # 2. Group pages by section
    groups = []
    current_group = []
    last_section = None
    
    for page, section in page_sections:
        if last_section is None:
            last_section = section
            current_group.append(page)
        elif section == last_section:
            current_group.append(page)
        else:
            groups.append((last_section, current_group))
            current_group = [page]
            last_section = section
            
    if current_group:
        groups.append((last_section, current_group))
        
    # 3. Process groups into chunks
    chunks = []
    registry = []
    
    for sect_type, pages in groups:
        start_page = pages[0]["page_number"]
        end_page = pages[-1]["page_number"]
        combined_text = "\n\n".join(p["text"] for p in pages)
        
        # Determine if any page in this group is scanned
        has_scanned = any(p.get("is_scanned", False) for p in pages)
        
        # Split specific sections further
        if sect_type == "AUDIT_REPORT":
            # Search for sub-headings
            sub_matches = []
            for sub_name, pattern in AUDIT_SUB_PATTERNS:
                for match in pattern.finditer(combined_text):
                    sub_matches.append((match.start(), sub_name))
                    
            if len(sub_matches) >= 2:
                # Sort matches by character index
                sub_matches.sort()
                
                # Add intro chunk
                intro_content = combined_text[:sub_matches[0][0]].strip()
                if intro_content:
                    c_id = f"{doc_stem}_audit_report_intro"
                    chunks.append({
                        "chunk_id": c_id,
                        "label": "Independent Auditor's Report - Introduction",
                        "type": "Auditor Report",
                        "content": intro_content,
                        "start_page": start_page,
                        "end_page": end_page,
                        "is_scanned": has_scanned,
                        "quality": "LOW" if has_scanned else "MED"
                    })
                    
                # Add sub-chunks
                for i in range(len(sub_matches)):
                    start_idx = sub_matches[i][0]
                    end_idx = sub_matches[i+1][0] if i+1 < len(sub_matches) else len(combined_text)
                    
                    sub_name = sub_matches[i][1]
                    sub_content = combined_text[start_idx:end_idx].strip()
                    clean_sub_name = sub_name.lower().replace(' ', '_').replace("'", "")
                    c_id = f"{doc_stem}_audit_report_{clean_sub_name}"
                    chunks.append({
                        "chunk_id": c_id,
                        "label": f"Auditor's Report - {sub_name}",
                        "type": "Auditor Report",
                        "content": sub_content,
                        "start_page": start_page,
                        "end_page": end_page,
                        "is_scanned": has_scanned,
                        "quality": "LOW" if has_scanned else "MED"
                    })
            else:
                # Fallback to single report chunk
                c_id = f"{doc_stem}_audit_report"
                chunks.append({
                    "chunk_id": c_id,
                    "label": "Independent Auditor's Report (Full)",
                    "type": "Auditor Report",
                    "content": combined_text,
                    "start_page": start_page,
                    "end_page": end_page,
                    "is_scanned": has_scanned,
                    "quality": "LOW" if has_scanned else "MED"
                })
                
        elif sect_type == "NOTES_FS":
            # Find offsets for notes headings
            note_matches = []
            for match in NOTE_HEADER_REGEX.finditer(combined_text):
                # Determine note number
                note_num = match.group(1) or match.group(2)
                title = match.group(3) or ""
                note_matches.append((match.start(), note_num, title))
                
            if len(note_matches) >= 2:
                note_matches.sort()
                
                # Intro chunk before first note
                intro_content = combined_text[:note_matches[0][0]].strip()
                if intro_content:
                    chunks.append({
                        "chunk_id": f"{doc_stem}_notes_intro",
                        "label": "Notes to Financial Statements - Introduction",
                        "type": "Notes",
                        "content": intro_content,
                        "start_page": start_page,
                        "end_page": end_page,
                        "is_scanned": has_scanned,
                        "quality": "LOW" if has_scanned else "MED"
                    })
                    
                # Notes sub-chunks
                for i in range(len(note_matches)):
                    start_idx = note_matches[i][0]
                    end_idx = note_matches[i+1][0] if i+1 < len(note_matches) else len(combined_text)
                    
                    note_num = note_matches[i][1]
                    note_title = note_matches[i][2].strip()
                    title_suffix = f": {note_title}" if note_title else ""
                    
                    note_content = combined_text[start_idx:end_idx].strip()
                    
                    chunks.append({
                        "chunk_id": f"{doc_stem}_note_{note_num}",
                        "label": f"Note {note_num}{title_suffix}",
                        "type": "Notes",
                        "content": note_content,
                        "start_page": start_page,
                        "end_page": end_page,
                        "is_scanned": has_scanned,
                        "quality": "LOW" if has_scanned else "MED"
                    })
            else:
                # Fallback to single notes chunk
                chunks.append({
                    "chunk_id": f"{doc_stem}_notes_full",
                    "label": "Notes to Financial Statements (Full)",
                    "type": "Notes",
                    "content": combined_text,
                    "start_page": start_page,
                    "end_page": end_page,
                    "is_scanned": has_scanned,
                    "quality": "LOW" if has_scanned else "MED"
                })
                
        else:
            # Standard single chunk for other section types
            labels_map = {
                "COVER": "Title & Cover Page",
                "TOC": "Table of Contents",
                "BALANCE_SHEET": "Balance Sheet / Statement of Net Position",
                "INCOME_STATEMENT": "Statement of Activities / Income Statement",
                "CASH_FLOW": "Statement of Cash Flows",
                "SEFA": "SEFA (Schedule of Expenditures of Federal Awards)",
                "NOTES_SEFA": "Notes to the SEFA",
                "YB_REPORT": "Yellow Book Report (Internal Control/Compliance)",
                "UG_REPORT": "Uniform Guidance Report (Compliance)",
                "FINDINGS": "Schedule of Findings and Questioned Costs",
                "ACTION_PLAN": "Corrective Action Plan",
            }
            
            c_label = labels_map.get(sect_type, f"Section - {sect_type}")
            c_type = "Statement" if "STATEMENT" in sect_type or "SHEET" in sect_type or sect_type == "SEFA" else "Report"
            if sect_type in ["COVER", "TOC"]:
                c_type = "Metadata"
                
            c_id = f"{doc_stem}_{sect_type.lower()}"
            
            # Perform mathematical audits on Balance Sheet
            audit_meta = {}
            quality = "LOW" if has_scanned else "MED"
            
            if sect_type == "BALANCE_SHEET":
                audit_meta = perform_balance_sheet_check(combined_text)
                if audit_meta.get("balanced") is True and not has_scanned:
                    quality = "HIGH"
                    
            chunks.append({
                "chunk_id": c_id,
                "label": c_label,
                "type": c_type,
                "content": combined_text,
                "start_page": start_page,
                "end_page": end_page,
                "is_scanned": has_scanned,
                "quality": quality,
                "audit_math": audit_meta
            })
            
    # 4. Generate Registry
    for c in chunks:
        registry.append({
            "chunk_id": c["chunk_id"],
            "label": c["label"],
            "type": c["type"],
            "start_page": c["start_page"],
            "end_page": c["end_page"],
            "char_count": len(c["content"]),
            "word_count": len(c["content"].split()),
            "quality": c["quality"],
            "ocr_needed": "YES" if c["is_scanned"] else "NO",
            "balance_check": c.get("audit_math", {}).get("message", "N/A")
        })
        
    return chunks, registry
