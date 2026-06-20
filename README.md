# Financial Statement & Single Audit Converter

A specialized document extraction, semantic chunking, and mathematical audit pipeline designed specifically for municipal, government, and non-profit **Single Audit Report Packages** (PDF, Excel, and Word files).

---

## 🚀 Key Features

* **Semantic Audit-Specific Chunking**: Automatically classifies and splits documents into specific audit components:
  * Title & Cover Pages
  * Table of Contents
  * Independent Auditor's Report (sub-chunked into Opinion, Basis, Management & Auditor Responsibilities, Supplementary Info)
  * Balance Sheet / Statement of Net Position
  * Statement of Activities (SOA) / Income Statement
  * Statement of Cash Flows
  * Notes to the Financial Statements (split into individual note numbers, e.g. Note 1, Note 2, etc.)
  * SEFA (Schedule of Expenditures of Federal Awards) & Notes to the SEFA
  * Yellow Book & Uniform Guidance compliance reports
  * Schedule of Findings and Questioned Costs & Corrective Action Plans
* **Grid-Preserving PDF Layouts**: Custom layout extraction sorts character positioning horizontally and vertically to prevent multi-column tabular data from merging or shuffling during PDF text parsing.
* **Balance Sheet Mathematical Verification**: Automatically executes double-entry check equations:
  $$\text{Total Assets} = \text{Total Liabilities} + \text{Net Assets / Equity}$$
  Verifies balance integrity and flags rounding discrepancies.
* **Automatic EasyOCR Fallback**: Detects scanned pages (such as physically signed auditor signatures or signed corrective action plan attachments). Automatically renders scanned pages to images in-memory and runs OCR to extract the text, ensuring no data is lost for downstream LLM parsing.
* **Audit Dashboard UI & CLI**: Choose between an executive-themed Flask web dashboard (with live logs, file queuing, interactive chunk indexes, and mathematical reports) or a scriptable command-line interface.

---

## 📁 Repository Structure

```text
├── app_server.py            # Flask web dashboard server (visual validation & logs)
├── convert.py               # CLI runner (supports single, batch, or test harness)
├── requirements.txt         # Package dependencies
├── .gitignore               # Excludes temp uploads, outputs, and cash files
├── converters/              # File parser engine modules
│   ├── pdf.py               # Grid text parser + EasyOCR image fallback
│   ├── excel.py             # Openpyxl sheet data converter
│   └── word.py              # Docx linear paragraph/table parser
├── core/                    # Core pipeline logic
│   ├── chunker.py           # Single Audit state-machine section classifier & math checks
│   └── writer.py            # Registry builder, compilation generator, and report styling
└── tests/                   # Validation harness directory
    └── ground_truth.json    # Verification template
```

---

## 🛠️ Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/fs-statement-converter.git
   cd fs-statement-converter
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: EasyOCR requires PyTorch and OpenCV. These will be installed automatically. On first run, the English OCR weights will download in the background).*

---

## 💻 How to Use

### 1. Launch the Web UI
Run the local web dashboard:
```bash
python app_server.py
```
Open [http://localhost:5000](http://localhost:5000) in your web browser. Drag and drop PDF, Word, or Excel reports, convert them, and preview mathematical indicators before downloading.

### 2. Command Line Interface (CLI)
For single-file scriptable extraction:
```bash
python convert.py <path_to_statement> [output_directory]
```

To run batch processing on an entire directory:
```bash
python convert.py --batch <path_to_input_directory>
```

To run the validation test suite (ground-truth chunk count checks):
```bash
python convert.py --test
```

---

## 📊 Output Artifacts

For each converted document, a standardized output folder is created:
1. `_full_text.txt`: A clean text compilation of the entire document. Chunks are demarcated with clear boundary headers (e.g. `----- START CHUNK: Note 1 -----`), optimized for Large Language Model (LLM) uploads.
2. `chunk_registry.xlsx`: A styled Excel worksheet serving as an index of all chunks, specifying page bounds, word counts, and quality metrics.
3. `extraction_report.xlsx`: A completeness scorecard displaying chunk KPIs, scanned page flags, and Balance Sheet math validation checks.
4. `registry.json`: Machine-readable database backup.
5. `/chunks/*.json`: Individual JSON files for database indexing.
