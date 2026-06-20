"""
FINANCIAL STATEMENT CONVERTER
==============================
Tailored document extraction tool for financial audits & Single Audits.
Parses Balance Sheets, Income Statements, Cash Flow Statements, and footnotes.

Usage:
    python convert.py <file_path> [output_dir]
    python convert.py --test          (runs validation harness on test files)
    python convert.py --batch <dir>   (converts all supported files in a directory)

Output per document:
    /output/<document_name>/
        chunk_registry.xlsx      ← master index, auditor-readable
        extraction_report.xlsx   ← completeness, quality, and math balancing summary
        registry.json            ← machine backup
        /chunks/
            <chunk_id>.json      ← one file per chunk, machine-ingestable
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Insert current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from converters.pdf   import extract_pdf
from converters.excel import extract_excel
from converters.word  import extract_word
from core.chunker     import chunk_document
from core.writer      import write_outputs

SUPPORTED_EXTENSIONS = {
    "pdf":  extract_pdf,
    "xlsx": extract_excel,
    "xls":  extract_excel,
    "docx": extract_word,
    "doc":  extract_word,
}


def convert_document(file_path: str, output_dir: str = None) -> dict:
    """
    Full pipeline: extract raw content → chunk into financial sections → write outputs.
    Returns a summary dict.
    """
    file_path = str(Path(file_path).resolve())

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: .{ext}\n"
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    if output_dir is None:
        base_name = Path(file_path).stem
        output_dir = os.path.join(
            os.path.dirname(file_path), f"{base_name}_converted"
        )

    print(f"\n→ Converting: {os.path.basename(file_path)}")
    print(f"  Output:     {output_dir}")

    # 1. Extract
    extractor = SUPPORTED_EXTENSIONS[ext]
    raw_doc = extractor(file_path)

    if "error" in raw_doc:
        print(f"  ✗ Extraction error: {raw_doc['error']}")
        return {"error": raw_doc["error"], "file": file_path}

    # 2. Chunk (Financial-statement-specific chunking)
    chunks, registry = chunk_document(raw_doc, file_path)

    # 3. Write outputs & reports
    result = write_outputs(chunks, registry, output_dir, file_path)
    result["file"] = file_path

    return result


def convert_batch(input_dir: str, output_base: str = None) -> list:
    """Convert all supported documents in a directory."""
    input_dir = str(Path(input_dir).resolve())
    if output_base is None:
        output_base = os.path.join(input_dir, "_converted")

    results = []
    files = [
        f for f in os.listdir(input_dir)
        if f.rsplit(".", 1)[-1].lower() in SUPPORTED_EXTENSIONS
        and not f.startswith("~")  # skip temp Excel files
    ]

    if not files:
        print(f"No supported files found in: {input_dir}")
        return results

    print(f"\nBatch conversion: {len(files)} files in {input_dir}")

    for fname in sorted(files):
        file_path = os.path.join(input_dir, fname)
        out_dir   = os.path.join(output_base, Path(fname).stem)
        try:
            result = convert_document(file_path, out_dir)
            results.append(result)
        except Exception as e:
            print(f"  ✗ Failed: {fname} — {e}")
            results.append({"file": file_path, "error": str(e)})

    # Summary
    passed  = sum(1 for r in results if "error" not in r)
    failed  = sum(1 for r in results if "error" in r)
    total_chunks = sum(r.get("total_chunks", 0) for r in results)

    print(f"\n{'─'*50}")
    print(f"Batch complete: {passed} succeeded / {failed} failed")
    print(f"Total chunks produced: {total_chunks}")

    return results


def run_validation_harness(test_dir: str):
    """
    Ground-truth validation harness.
    Compares actual chunk names and counts against ground_truth.json.
    """
    gt_path = os.path.join(test_dir, "ground_truth.json")

    if not os.path.exists(gt_path):
        print(f"\nNo ground_truth.json found in {test_dir}")
        print("Creating template ground_truth.json — fill in expected values.")
        _create_gt_template(test_dir)
        return

    with open(gt_path) as f:
        ground_truth = json.load(f)

    print(f"\n{'═'*60}")
    print(f"VALIDATION HARNESS — {len(ground_truth)} test documents")
    print(f"{'═'*60}")

    results = []

    for test_case in ground_truth:
        fname    = test_case["file"]
        expected = test_case.get("expected_chunks")
        notes    = test_case.get("notes", "")
        file_path = os.path.join(test_dir, fname)

        if not os.path.exists(file_path):
            print(f"\n  SKIP  {fname} — file not found")
            results.append({"file": fname, "result": "SKIP"})
            continue

        try:
            out_dir = os.path.join(test_dir, "_validation", Path(fname).stem)
            result  = convert_document(file_path, out_dir)
            actual  = result.get("total_chunks", 0)

            if expected is None:
                status = "INFO"
                status_str = f"  INFO  {fname}: {actual} chunks produced (no expected count set)"
            elif actual == expected:
                status = "PASS"
                status_str = f"  PASS  {fname}: {actual}/{expected} chunks ✓"
            else:
                status = "FAIL"
                status_str = (
                    f"  FAIL  {fname}: got {actual} chunks, expected {expected}"
                    + (f" — {notes}" if notes else "")
                )

            print(status_str)
            results.append({
                "file":     fname,
                "expected": expected,
                "actual":   actual,
                "result":   status,
                "quality_high": result.get("quality_high", 0),
                "quality_med":  result.get("quality_med",  0),
                "quality_low":  result.get("quality_low",  0),
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ERROR {fname}: {e}")
            results.append({"file": fname, "result": "ERROR", "error": str(e)})

    # Final score
    passed  = sum(1 for r in results if r["result"] == "PASS")
    failed  = sum(1 for r in results if r["result"] == "FAIL")
    errors  = sum(1 for r in results if r["result"] == "ERROR")

    print(f"\n{'─'*60}")
    print(f"Results: {passed} PASS / {failed} FAIL / {errors} ERROR")
    print(f"{'═'*60}\n")

    return results


def _create_gt_template(test_dir: str):
    """Create a blank ground_truth.json template."""
    os.makedirs(test_dir, exist_ok=True)
    supported = list(SUPPORTED_EXTENSIONS.keys())
    files = [
        f for f in os.listdir(test_dir)
        if f.rsplit(".", 1)[-1].lower() in supported
        and not f.startswith("~")
    ]
    template = [
        {
            "file": fname,
            "expected_chunks": None,
            "expected_entity_type": "Single Audit Package",
            "notes": ""
        }
        for fname in sorted(files)
    ]
    out_path = os.path.join(test_dir, "ground_truth.json")
    with open(out_path, "w") as f:
        json.dump(template, f, indent=2)
    print(f"Template written to: {out_path}")
    print("Fill in 'expected_chunks' for each file, then re-run --test")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Statement & Single Audit Converter CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("file",         nargs="?", help="File to convert")
    parser.add_argument("output_dir",   nargs="?", help="Output directory (optional)")
    parser.add_argument("--batch",      metavar="DIR", help="Convert all files in directory")
    parser.add_argument("--test",       metavar="DIR", nargs="?", const="./tests",
                        help="Run validation harness (default: ./tests)")

    args = parser.parse_args()

    if args.test:
        run_validation_harness(args.test)
    elif args.batch:
        convert_batch(args.batch)
    elif args.file:
        result = convert_document(args.file, args.output_dir)
        if "error" not in result:
            print(f"\n  Chunks: {result['total_chunks']}")
            print(f"  Output: {result['output_dir']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
