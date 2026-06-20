import os
import sys
import json
import threading
import webbrowser
import time
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string

# Add current dir to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from convert import convert_document

app = Flask(__name__)

# ── Storage ───────────────────────────────────────────────────
UPLOAD_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_uploads")
OUTPUT_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_web_output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls", "docx", "doc"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── HTML Template ─────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FS & Single Audit Converter</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --ink:           #14171f;
    --paper:         #FAF8F5;
    --card-bg:       #ffffff;
    --accent:        #1A3A5C;
    --accent-light:  #2B527A;
    --gold:          #C5A059;
    --gold-light:    #E5C07B;
    --rule:          #E6E2DA;
    --shadow:        rgba(26, 58, 92, 0.08);
    --hover-shadow:  rgba(26, 58, 92, 0.15);
    
    --pass:          #2A6F43;
    --pass-bg:       #E8F5E9;
    --warn:          #B86200;
    --warn-bg:       #FFF3E0;
    --fail:          #9E2A2B;
    --fail-bg:       #FFEBEE;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Outfit', sans-serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    line-height: 1.5;
  }

  /* ── Header ── */
  header {
    background: var(--accent);
    background: linear-gradient(135deg, var(--accent) 0%, #0F233B 100%);
    color: white;
    padding: 32px 48px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 5px solid var(--gold);
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
  }
  .header-title {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  header h1 {
    font-size: 1.8rem;
    font-weight: 700;
    letter-spacing: -0.01em;
  }
  header h1 span {
    color: var(--gold);
  }
  header .version {
    font-size: 0.75rem;
    font-family: 'Fira Code', monospace;
    opacity: 0.7;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .header-badge {
    background: rgba(197, 160, 89, 0.15);
    border: 1px solid var(--gold);
    color: var(--gold-light);
    padding: 6px 14px;
    border-radius: 50px;
    font-size: 0.78rem;
    font-family: 'Fira Code', monospace;
    letter-spacing: 0.05em;
  }

  /* ── Main Layout ── */
  main {
    max-width: 1100px;
    width: 100%;
    margin: 0 auto;
    padding: 40px 24px;
    flex: 1;
  }

  /* ── Drop Zone ── */
  .drop-zone {
    border: 2px dashed #C0B7A6;
    border-radius: 8px;
    padding: 64px 32px;
    text-align: center;
    cursor: pointer;
    background: var(--card-bg);
    box-shadow: 0 4px 12px var(--shadow);
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
    position: relative;
    overflow: hidden;
  }
  .drop-zone:hover, .drop-zone.dragover {
    border-color: var(--accent);
    background: #F4F7FA;
    transform: translateY(-2px);
    box-shadow: 0 6px 20px var(--hover-shadow);
  }
  .drop-zone input[type=file] {
    position: absolute;
    inset: 0;
    opacity: 0;
    cursor: pointer;
    width: 100%;
    height: 100%;
  }
  .drop-icon {
    font-size: 3rem;
    margin-bottom: 20px;
    display: inline-block;
    filter: drop-shadow(0 4px 6px rgba(0,0,0,0.1));
  }
  .drop-zone h2 {
    font-size: 1.5rem;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--accent);
  }
  .drop-zone p {
    font-size: 0.88rem;
    color: #6A6E75;
    margin-bottom: 24px;
  }
  .drop-zone .formats {
    display: flex;
    gap: 12px;
    justify-content: center;
    flex-wrap: wrap;
  }
  .format-tag {
    background: var(--accent);
    color: white;
    font-size: 0.7rem;
    font-family: 'Fira Code', monospace;
    padding: 4px 12px;
    border-radius: 4px;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    box-shadow: 0 2px 4px rgba(0,0,0,0.08);
  }

  /* ── File Queue ── */
  #file-queue {
    margin-top: 24px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .file-item {
    background: var(--card-bg);
    border: 1px solid var(--rule);
    border-radius: 6px;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 2px 6px var(--shadow);
    animation: slideIn 0.3s ease-out;
  }
  @keyframes slideIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .file-icon { font-size: 1.5rem; }
  .file-details {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: 12px;
  }
  .file-name {
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--accent);
  }
  .file-size {
    color: #888;
    font-size: 0.78rem;
    font-family: 'Fira Code', monospace;
  }
  .file-remove {
    background: none;
    border: none;
    cursor: pointer;
    color: #ABB2BF;
    font-size: 1.2rem;
    padding: 4px 8px;
    border-radius: 4px;
    transition: all 0.2s;
  }
  .file-remove:hover {
    color: var(--fail);
    background: var(--fail-bg);
  }

  /* ── Actions ── */
  .action-row {
    margin-top: 32px;
    display: flex;
    gap: 16px;
    align-items: center;
  }
  .btn {
    font-family: inherit;
    font-weight: 600;
    font-size: 0.9rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    cursor: pointer;
    border-radius: 6px;
    padding: 14px 36px;
    transition: all 0.2s cubic-bezier(0.25, 0.8, 0.25, 1);
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .btn-primary {
    background: var(--accent);
    color: white;
    border: none;
    box-shadow: 0 4px 12px rgba(26,58,92,0.25);
  }
  .btn-primary:hover:not(:disabled) {
    background: var(--accent-light);
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(26,58,92,0.35);
  }
  .btn-primary:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .btn-secondary {
    background: transparent;
    border: 1px solid var(--rule);
    color: #555;
  }
  .btn-secondary:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--card-bg);
  }

  /* ── Progress / Console ── */
  #progress-section {
    margin-top: 40px;
    display: none;
  }
  .section-label {
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--accent);
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .progress-bar-outer {
    height: 8px;
    background: var(--rule);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
  }
  .progress-bar-inner {
    height: 100%;
    background: linear-gradient(90deg, var(--gold) 0%, var(--accent) 100%);
    width: 0%;
    transition: width 0.3s ease;
  }
  .console-log {
    background: #1e222b;
    color: #abb2bf;
    font-family: 'Fira Code', monospace;
    font-size: 0.8rem;
    padding: 20px;
    border-radius: 8px;
    height: 180px;
    overflow-y: auto;
    line-height: 1.6;
    box-shadow: inset 0 2px 8px rgba(0,0,0,0.3);
    border: 1px solid #282c34;
  }
  .log-line { display: block; }
  .log-line.log-success { color: #98c379; }
  .log-line.log-warn    { color: #e5c07b; }
  .log-line.log-err     { color: #e06c75; }

  /* ── Results Cards ── */
  #results-section {
    margin-top: 48px;
    display: none;
  }
  .result-card {
    background: var(--card-bg);
    border: 1px solid var(--rule);
    border-radius: 8px;
    margin-bottom: 24px;
    box-shadow: 0 4px 15px var(--shadow);
    overflow: hidden;
    transition: box-shadow 0.3s;
  }
  .result-card:hover {
    box-shadow: 0 6px 22px var(--hover-shadow);
  }
  .result-card-header {
    padding: 20px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    border-bottom: 1px solid var(--rule);
    background: #fdfdfd;
  }
  .result-title-container {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .status-badge {
    font-size: 0.72rem;
    font-weight: 700;
    font-family: 'Fira Code', monospace;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 4px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }
  .status-pass { background: var(--pass-bg); color: var(--pass); }
  .status-warn { background: var(--warn-bg); color: var(--warn); }
  .status-fail { background: var(--fail-bg); color: var(--fail); }
  
  .result-filename {
    font-weight: 700;
    font-size: 1.1rem;
    color: var(--accent);
  }

  /* ── KPI Dashboard Grid ── */
  .kpi-grid {
    padding: 24px 28px;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 16px;
    border-bottom: 1px solid var(--rule);
    background: #FAF9F6;
  }
  .kpi-card {
    background: white;
    border: 1px solid var(--rule);
    border-radius: 6px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 4px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  }
  .kpi-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #888;
  }
  .kpi-value {
    font-size: 1.4rem;
    font-weight: 700;
    color: var(--ink);
  }
  .kpi-subtext {
    font-size: 0.72rem;
    color: #666;
  }
  
  /* ── Interactive Chunk Registry ── */
  .details-btn-container {
    padding: 12px 28px;
    background: #FAF9F6;
    border-bottom: 1px solid var(--rule);
    display: flex;
    justify-content: flex-end;
  }
  .toggle-details-btn {
    background: none;
    border: none;
    color: var(--accent);
    cursor: pointer;
    font-weight: 600;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .toggle-details-btn:hover {
    color: var(--gold);
    text-decoration: underline;
  }
  
  .chunk-registry-panel {
    display: none;
    padding: 24px 28px;
    background: white;
    border-bottom: 1px solid var(--rule);
    overflow-x: auto;
    animation: fadeIn 0.3s;
  }
  @keyframes fadeIn {
    from { opacity: 0; } to { opacity: 1; }
  }
  .chunk-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    text-align: left;
  }
  .chunk-table th, .chunk-table td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--rule);
  }
  .chunk-table th {
    background: #F4F7FA;
    font-weight: 600;
    color: var(--accent);
  }
  .chunk-table tr:hover td {
    background: #FAF8F5;
  }
  
  /* ── Downloads Bar ── */
  .result-downloads {
    padding: 20px 28px;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
    background: #F4F7FA;
  }
  .dl-link {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: white;
    border: 1px solid var(--rule);
    padding: 10px 18px;
    font-size: 0.82rem;
    font-weight: 600;
    cursor: pointer;
    border-radius: 6px;
    text-decoration: none;
    color: var(--ink);
    transition: all 0.2s;
    box-shadow: 0 2px 4px rgba(0,0,0,0.02);
  }
  .dl-link:hover {
    border-color: var(--accent);
    color: var(--accent);
    background: #FAFBFD;
    transform: translateY(-1px);
    box-shadow: 0 4px 8px rgba(0,0,0,0.05);
  }
  .dl-link.primary {
    background: var(--accent);
    color: white;
    border-color: var(--accent);
    box-shadow: 0 2px 8px rgba(26,58,92,0.15);
  }
  .dl-link.primary:hover {
    background: var(--accent-light);
    box-shadow: 0 4px 12px rgba(26,58,92,0.25);
  }

  /* ── Guide / Instructions ── */
  .instructions-box {
    background: var(--card-bg);
    border: 1px solid var(--rule);
    border-left: 5px solid var(--gold);
    border-radius: 8px;
    padding: 28px 32px;
    font-size: 0.88rem;
    line-height: 1.8;
    box-shadow: 0 4px 12px var(--shadow);
    margin-top: 40px;
  }
  .instructions-box h3 {
    font-size: 1.15rem;
    font-weight: 700;
    margin-bottom: 12px;
    color: var(--accent);
  }
  .instructions-box ol { padding-left: 20px; }
  .instructions-box li { margin-bottom: 8px; }
  .instructions-box code {
    background: #F0EDE6;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.8rem;
    font-family: 'Fira Code', monospace;
    font-weight: 500;
  }

  /* ── Spinner ── */
  @keyframes spin { to { transform: rotate(360deg); } }
  .spinner {
    display: inline-block;
    width: 16px; height: 16px;
    border: 2px solid rgba(255,255,255,0.3);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  footer {
    text-align: center;
    padding: 32px;
    font-size: 0.72rem;
    color: #888;
    letter-spacing: 0.05em;
    border-top: 1px solid var(--rule);
    margin-top: 64px;
    background: white;
  }
</style>
</head>
<body>

<header>
  <div class="header-title">
    <h1>FS & Single Audit <span>Converter</span></h1>
    <span class="version">v1.0 · AUDIT-OS ENGINE</span>
  </div>
  <div class="header-badge">STABLE PIPELINE</div>
</header>

<main>

  <!-- Drop zone -->
  <div class="drop-zone" id="drop-zone">
    <input type="file" id="file-input" multiple accept=".pdf,.xlsx,.xls,.docx,.doc">
    <span class="drop-icon">📁</span>
    <h2>Drop Single Audit Reports or Statements</h2>
    <p>Supports financial PDF packages, Excel worksheets, or Word narratives</p>
    <div class="formats">
      <span class="format-tag">PDF Statement Package</span>
      <span class="format-tag">Excel Ledger</span>
      <span class="format-tag">Word Audit Note</span>
    </div>
  </div>

  <!-- File queue -->
  <div id="file-queue"></div>

  <!-- Action row -->
  <div class="action-row">
    <button id="convert-btn" class="btn btn-primary" disabled>Convert Documents</button>
    <button class="btn btn-secondary" id="clear-btn">Clear All</button>
  </div>

  <!-- Progress -->
  <div id="progress-section">
    <div class="section-label">Conversion Progress</div>
    <div class="progress-bar-outer">
      <div class="progress-bar-inner" id="progress-bar"></div>
    </div>
    <div class="console-log" id="progress-log"></div>
  </div>

  <!-- Results -->
  <div id="results-section">
    <div class="section-label" style="margin-bottom: 20px;">Processed Reports</div>
    <div id="results-list"></div>
  </div>

  <!-- Instructions -->
  <div class="instructions-box">
    <h3>Single Audit Report & LLM Ingestion Instructions</h3>
    <ol>
      <li>Drag and drop your complete municipal or non-profit financial statement document (PDF/Excel/Word).</li>
      <li>Click <code>Convert Documents</code>. The converter will isolate the Title page, TOC, Auditor's Opinion, Balance Sheets, Notes to the Financial Statements, SEFA, Yellow Book reports, and Questioned Findings into standard segments.</li>
      <li>Once complete, download the <code>chunk_registry.xlsx</code> (provides a structural summary for your auditor index) and the <code>full_text.txt</code> file.</li>
      <li>Upload the <code>full_text.txt</code> file to your LLM workspace. Because chunks are split semantically by Note number and report header, you can query: <em>"Find the pension liabilities in Note 8"</em> or <em>"Summarize finding 2025-001 in the Schedule of Findings"</em> and receive highly accurate citations.</li>
    </ol>
  </div>

</main>

<footer>AUDIT-OS · FS Statement & Single Audit Converter · Secure Local Workspace</footer>

<script>
  const dropZone   = document.getElementById('drop-zone');
  const fileInput  = document.getElementById('file-input');
  const fileQueue  = document.getElementById('file-queue');
  const convertBtn = document.getElementById('convert-btn');
  const clearBtn   = document.getElementById('clear-btn');
  const progressSection = document.getElementById('progress-section');
  const progressBar     = document.getElementById('progress-bar');
  const progressLog     = document.getElementById('progress-log');
  const resultsSection  = document.getElementById('results-section');
  const resultsList     = document.getElementById('results-list');

  let selectedFiles = [];

  // ── Drag and drop ──────────────────────────────────────────
  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('dragover');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    addFiles(Array.from(e.dataTransfer.files));
  });
  fileInput.addEventListener('change', () => {
    addFiles(Array.from(fileInput.files));
    fileInput.value = '';
  });

  function addFiles(files) {
    const allowed = ['pdf','xlsx','xls','docx','doc'];
    files.forEach(f => {
      const ext = f.name.split('.').pop().toLowerCase();
      if (allowed.includes(ext) && !selectedFiles.find(x => x.name === f.name)) {
        selectedFiles.push(f);
      }
    });
    renderQueue();
  }

  function renderQueue() {
    fileQueue.innerHTML = '';
    selectedFiles.forEach((f, i) => {
      const size = f.size > 1024*1024
        ? (f.size/1024/1024).toFixed(1) + ' MB'
        : (f.size/1024).toFixed(0) + ' KB';
      
      const fileExt = f.name.split('.').pop().toLowerCase();
      let icon = '📄';
      if (fileExt === 'pdf') icon = '📕';
      else if (fileExt === 'xlsx' || fileExt === 'xls') icon = '📗';
      else if (fileExt === 'docx' || fileExt === 'doc') icon = '📘';
      
      const div = document.createElement('div');
      div.className = 'file-item';
      div.innerHTML = `
        <span class="file-icon">${icon}</span>
        <div class="file-details">
          <span class="file-name">${f.name}</span>
          <span class="file-size">${size}</span>
        </div>
        <button class="file-remove" data-i="${i}" title="Remove file">✕</button>
      `;
      fileQueue.appendChild(div);
    });
    
    fileQueue.querySelectorAll('.file-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        selectedFiles.splice(parseInt(btn.dataset.i), 1);
        renderQueue();
      });
    });
    convertBtn.disabled = selectedFiles.length === 0;
  }

  clearBtn.addEventListener('click', () => {
    selectedFiles = [];
    renderQueue();
    progressSection.style.display = 'none';
    resultsSection.style.display  = 'none';
  });

  // ── Conversion ─────────────────────────────────────────────
  convertBtn.addEventListener('click', async () => {
    if (selectedFiles.length === 0) return;

    convertBtn.disabled = true;
    convertBtn.innerHTML = '<span class="spinner"></span> Converting...';
    progressSection.style.display = 'block';
    resultsSection.style.display  = 'none';
    progressLog.innerHTML = '';
    progressBar.style.width = '0%';
    resultsList.innerHTML  = '';

    const results = [];
    const total = selectedFiles.length;

    for (let i = 0; i < selectedFiles.length; i++) {
      const f = selectedFiles[i];
      logLine(`→ Launching extraction pipeline for: ${f.name}`);
      progressBar.style.width = ((i / total) * 100) + '%';

      try {
        const formData = new FormData();
        formData.append('file', f);

        const resp = await fetch('/convert', { method: 'POST', body: formData });
        const data = await resp.json();

        if (data.error) {
          logLine(`  ✗ Error: ${data.error}`, 'err');
          results.push({ file: f.name, error: data.error });
        } else {
          const q = `${data.quality_high} HIGH / ${data.quality_med} MED / ${data.quality_low} LOW`;
          logLine(`  ✓ ${data.total_chunks} audit chunks isolated — (${q})`, 'success');
          if (data.ocr_chunks > 0 && data.registry) {
            data.registry.forEach(c => {
              if (c.ocr_needed === "YES") {
                logLine(`  ⚠ Warning: Chunk "${c.label}" (pages ${c.start_page}–${c.end_page}) contains scanned images with no selectable text.`, 'warn');
              }
            });
          }
          results.push({ file: f.name, ...data });
        }
      } catch(err) {
        logLine(`  ✗ Request failure: ${err.message}`, 'err');
        results.push({ file: f.name, error: err.message });
      }
    }

    progressBar.style.width = '100%';
    logLine('✓ All documents processed successfully.', 'success');

    convertBtn.disabled = false;
    convertBtn.innerHTML = 'Convert Documents';

    showResults(results);
  });

  function logLine(msg, type='') {
    const span = document.createElement('span');
    span.className = 'log-line' + (type ? ' log-' + type : '');
    span.textContent = msg;
    progressLog.appendChild(span);
    progressLog.scrollTop = progressLog.scrollHeight;
  }

  function showResults(results) {
    resultsSection.style.display = 'block';
    resultsList.innerHTML = '';

    results.forEach((r, r_idx) => {
      const hasError = !!r.error;
      const hasOcr   = r.ocr_chunks > 0;
      
      // Determine balance status text
      let balanceLabel = "N/A";
      let balanceClass = "status-warn";
      let mathChecked = false;
      
      if (!hasError && r.registry) {
        const bs_chunk = r.registry.find(c => c.chunk_id.includes('_balance_sheet'));
        if (bs_chunk && bs_chunk.balance_check) {
          mathChecked = true;
          if (bs_chunk.balance_check.includes("Balanced!")) {
             balanceLabel = "BALANCED";
             balanceClass = "status-pass";
          } else if (bs_chunk.balance_check.includes("Mismatched!")) {
             balanceLabel = "MATH MISMATCH";
             balanceClass = "status-fail";
          } else {
             balanceLabel = "UNVERIFIED";
             balanceClass = "status-warn";
          }
        }
      }

      const status = hasError ? 'fail' : hasOcr ? 'warn' : 'pass';
      const statusLabel = hasError ? 'ERROR' : hasOcr ? 'REVIEW' : 'PASS';

      const card = document.createElement('div');
      card.className = 'result-card';

      let dashboardHtml = '';
      let chunkTableHtml = '';
      let downloadsHtml = '';

      if (!hasError) {
        dashboardHtml = `
          <div class="kpi-grid">
            <div class="kpi-card">
              <span class="kpi-label">Isolated Chunks</span>
              <span class="kpi-value">${r.total_chunks}</span>
              <span class="kpi-subtext">Statement sections & notes</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">High Quality</span>
              <span class="kpi-value" style="color:var(--pass)">${r.quality_high}</span>
              <span class="kpi-subtext">Tabular and parsed sheets</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">OCR Recommended</span>
              <span class="kpi-value" style="${hasOcr ? 'color:var(--warn)' : ''}">${r.ocr_chunks}</span>
              <span class="kpi-subtext">Scanned or empty pages</span>
            </div>
            <div class="kpi-card">
              <span class="kpi-label">Math Check</span>
              <span class="kpi-value ${balanceClass}" style="display:inline-block; font-size: 0.82rem; padding: 4px 8px; border-radius: 4px; text-align: center; font-weight:700; width:fit-content; margin-top:4px;">${balanceLabel}</span>
              <span class="kpi-subtext">Assets = Liab + Equity</span>
            </div>
          </div>`;
          
        // Build table of chunks
        let rowsHtml = '';
        r.registry.forEach(c => {
          const isNote = c.type === 'Notes';
          const typeColor = isNote ? 'color:#4F7CAC; font-weight:500;' : '';
          const mathIndicator = c.balance_check !== "N/A" ? `<span style="font-size:0.75rem; font-family:'Fira Code', monospace; color: ${c.balance_check.includes('Balanced!') ? 'var(--pass)' : 'var(--fail)'}">${c.balance_check}</span>` : '—';
          
          rowsHtml += `
            <tr>
              <td><span style="font-family:'Fira Code', monospace; font-size:0.75rem;">${c.chunk_id}</span></td>
              <td><strong>${c.label}</strong></td>
              <td><span style="${typeColor}">${c.type}</span></td>
              <td style="text-align:center;">p. ${c.start_page}–${c.end_page}</td>
              <td style="text-align:center;">${c.word_count}</td>
              <td style="text-align:center;"><span class="status-badge status-${c.quality.toLowerCase()}" style="font-size:0.65rem; padding:2px 8px;">${c.quality}</span></td>
              <td>${mathIndicator}</td>
            </tr>`;
        });
        
        chunkTableHtml = `
          <div class="details-btn-container">
            <button class="toggle-details-btn" data-target="panel-${r_idx}">
              👁 View Chunk Details Table & Math Audits
            </button>
          </div>
          <div class="chunk-registry-panel" id="panel-${r_idx}">
            <h4 style="margin-bottom:12px; color:var(--accent); font-size:0.95rem;">Extracted Chunk Registry (${r.total_chunks} Chunks)</h4>
            <table class="chunk-table">
              <thead>
                <tr>
                  <th>Chunk ID</th>
                  <th>Label</th>
                  <th>Type</th>
                  <th style="text-align:center;">Pages</th>
                  <th style="text-align:center;">Words</th>
                  <th style="text-align:center;">Quality</th>
                  <th>Audit Balance Check</th>
                </tr>
              </thead>
              <tbody>
                ${rowsHtml}
              </tbody>
            </table>
          </div>`;

        const job_id = r.job_id;
        downloadsHtml = `
          <div class="result-downloads">
            <a class="dl-link primary" href="/download/${job_id}/registry">📥 download chunk_registry.xlsx</a>
            <a class="dl-link primary" href="/download/${job_id}/fulltext">📥 download full_text.txt</a>
            <a class="dl-link" href="/download/${job_id}/report">📥 download completeness_report.xlsx</a>
          </div>`;
      }

      card.innerHTML = `
        <div class="result-card-header">
          <div class="result-title-container">
            <span class="status-badge status-${status}">${statusLabel}</span>
            <span class="result-filename">${r.file}</span>
          </div>
        </div>
        ${dashboardHtml}
        ${hasError ? `<div style="padding:20px 28px;font-size:0.85rem;color:var(--fail);background:var(--fail-bg);font-family:'Fira Code', monospace;">${r.error}</div>` : ''}
        ${chunkTableHtml}
        ${downloadsHtml}
      `;

      resultsList.appendChild(card);
    });
    
    // Add toggles
    document.querySelectorAll('.toggle-details-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const panel = document.getElementById(btn.dataset.target);
        if (panel.style.display === 'block') {
          panel.style.display = 'none';
          btn.innerHTML = '👁 View Chunk Details Table & Math Audits';
        } else {
          panel.style.display = 'block';
          btn.innerHTML = '🙈 Hide Chunk Details Table';
        }
      });
    });
  }
</script>
</body>
</html>
"""


# ── Job storage (in-memory for this session) ──────────────────
jobs = {}


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/convert", methods=["POST"])
def convert():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename):
        return jsonify({"error": f"Unsupported file type: {f.filename}"}), 400

    # Save upload
    job_id   = str(uuid.uuid4())[:8]
    safe_name = Path(f.filename).name
    upload_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_name}")
    f.save(upload_path)

    # Output directory
    doc_stem = Path(safe_name).stem
    out_dir  = os.path.join(OUTPUT_DIR, f"{job_id}_{doc_stem}")

    try:
        result = convert_document(upload_path, out_dir)
        result["job_id"] = job_id

        # Load registry detail JSON to send back to frontend dashboard
        reg_json_path = os.path.join(out_dir, "registry.json")
        if os.path.exists(reg_json_path):
            with open(reg_json_path, "r", encoding="utf-8") as rf:
                result["registry"] = json.load(rf)
        else:
            result["registry"] = []

        # Store paths for download
        jobs[job_id] = {
            "registry":  os.path.join(out_dir, "chunk_registry.xlsx"),
            "report":    os.path.join(out_dir, "extraction_report.xlsx"),
            "fulltext":  _find_fulltext(out_dir),
        }

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

    finally:
        # Clean up upload file
        if os.path.exists(upload_path):
            os.remove(upload_path)


def _find_fulltext(out_dir):
    """Find the full text file in the output directory."""
    for fname in os.listdir(out_dir):
        if fname.endswith("_full_text.txt"):
            return os.path.join(out_dir, fname)
    return None


@app.route("/download/<job_id>/<file_type>")
def download(job_id, file_type):
    if job_id not in jobs:
        return "Job not found", 404

    paths = jobs[job_id]

    if file_type == "registry":
        path = paths.get("registry")
    elif file_type == "report":
        path = paths.get("report")
    elif file_type == "fulltext":
        path = paths.get("fulltext")
    else:
        return "Unknown file type", 400

    if not path or not os.path.exists(path):
        return "File not found", 404

    return send_file(path, as_attachment=True)


# ── Launch ────────────────────────────────────────────────────

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  FS & Single Audit Converter Server")
    print("  Starting at: http://localhost:5000")
    print("  Press Ctrl+C to stop")
    print("="*60 + "\n")

    # Auto-open browser
    threading.Thread(target=open_browser, daemon=True).start()

    app.run(host="0.0.0.0", port=5000, debug=False)
