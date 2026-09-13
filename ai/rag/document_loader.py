"""
Universal Document Loader for Sovereign AI Workbench (SIH26117).
Extracts text and page/slide/sheet metadata across:
- PDF (.pdf)
- DOCX / DOC (.docx, .doc)
- XLSX / XLS (.xlsx, .xls)
- CSV (.csv)
- PPTX / PPT (.pptx, .ppt)
- Plain Text (.txt, .md, .text, .log)

Includes zero-dependency standard-library fallbacks (zipfile + xml.etree.ElementTree + csv)
so documents are successfully parsed and indexed even if optional packages are missing.
"""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

def _load_pdf_entry(path: Path) -> List[Dict[str, Any]]:
    try:
        from ai.rag.pdf_loader import load_pdf
        return load_pdf(path)
    except Exception:
        return []


SUPPORTED_DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".doc",
    ".pptx",
    ".ppt",
    ".xlsx",
    ".xls",
    ".csv",
    ".txt",
    ".md",
    ".text",
    ".log",
}


# ============================================================
# DOCX EXTRACTOR
# ============================================================

def _extract_docx(file_path: Path) -> List[Dict[str, Any]]:
    """Extracts text from DOCX using python-docx if available, else zipfile + XML."""
    file_path = Path(file_path)

    # 1. Try python-docx
    try:
        import docx
        doc = docx.Document(str(file_path))
        paragraphs = []
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                paragraphs.append(txt)
        for tbl in doc.tables:
            for row in tbl.rows:
                row_txt = " | ".join([cell.text.strip() for cell in row.cells if cell.text.strip()])
                if row_txt:
                    paragraphs.append(row_txt)

        if paragraphs:
            return _paginate_paragraphs(paragraphs, file_path.name, words_per_page=450)
    except Exception:
        pass

    # 2. Pure Python fallback via zipfile and XML
    try:
        with zipfile.ZipFile(str(file_path), "r") as z:
            xml_content = z.read("word/document.xml")
            tree = ET.fromstring(xml_content)
            # Namespace for WordprocessingML
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

            paragraphs = []
            for p in tree.iter(f"{{{ns['w']}}}p"):
                texts = [node.text for node in p.iter(f"{{{ns['w']}}}t") if node.text]
                p_text = "".join(texts).strip()
                if p_text:
                    paragraphs.append(p_text)

            # Also check table rows
            for tr in tree.iter(f"{{{ns['w']}}}tr"):
                cells = []
                for tc in tr.iter(f"{{{ns['w']}}}tc"):
                    c_texts = [node.text for node in tc.iter(f"{{{ns['w']}}}t") if node.text]
                    c_str = "".join(c_texts).strip()
                    if c_str:
                        cells.append(c_str)
                if cells:
                    paragraphs.append(" | ".join(cells))

            if paragraphs:
                return _paginate_paragraphs(paragraphs, file_path.name, words_per_page=450)
    except Exception as e:
        pass

    # Fallback to plain text read if it was a plain file with wrong extension
    return _extract_txt(file_path)


def _paginate_paragraphs(paragraphs: List[str], source_name: str, words_per_page: int = 450) -> List[Dict[str, Any]]:
    pages = []
    current_page_paras = []
    current_word_count = 0
    page_num = 1

    for p in paragraphs:
        w_count = len(p.split())
        if current_word_count + w_count > words_per_page and current_page_paras:
            pages.append({
                "text": "\n\n".join(current_page_paras),
                "metadata": {
                    "source": source_name,
                    "page": page_num
                }
            })
            page_num += 1
            current_page_paras = [p]
            current_word_count = w_count
        else:
            current_page_paras.append(p)
            current_word_count += w_count

    if current_page_paras:
        pages.append({
            "text": "\n\n".join(current_page_paras),
            "metadata": {
                "source": source_name,
                "page": page_num
            }
        })

    return pages


# ============================================================
# CSV EXTRACTOR
# ============================================================

def _extract_csv(file_path: Path) -> List[Dict[str, Any]]:
    """Extracts CSV data, computes column stats, and produces structured searchable text."""
    file_path = Path(file_path)
    content = ""
    for enc in ("utf-8", "utf-8-sig", "latin1", "cp1252"):
        try:
            content = file_path.read_text(encoding=enc)
            break
        except Exception:
            continue

    if not content:
        return []

    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return []

    # Detect delimiter
    delimiter = ","
    try:
        dialect = csv.Sniffer().sniff(content[:4096])
        delimiter = dialect.delimiter
    except Exception:
        if "\t" in lines[0]:
            delimiter = "\t"
        elif ";" in lines[0]:
            delimiter = ";"

    reader = csv.reader(lines, delimiter=delimiter)
    all_rows = list(reader)
    if not all_rows:
        return []

    header = [h.strip() for h in all_rows[0]]
    data_rows = all_rows[1:]
    total_records = len(data_rows)

    # Compute numerical & categorical summaries
    col_data: Dict[str, List[str]] = {col: [] for col in header}
    for row in data_rows:
        for idx, col in enumerate(header):
            val = row[idx].strip() if idx < len(row) else ""
            if val:
                col_data[col].append(val)

    stats_lines = []
    for col, values in col_data.items():
        if not values:
            continue
        # Try numeric conversion
        nums = []
        for v in values:
            try:
                nums.append(float(v.replace(",", "").replace("$", "").replace("%", "")))
            except ValueError:
                pass

        if nums and len(nums) >= max(1, len(values) * 0.7):
            min_v = min(nums)
            max_v = max(nums)
            avg_v = sum(nums) / len(nums)
            sum_v = sum(nums)
            # Format nicely if integer
            min_str = int(min_v) if min_v.is_integer() else f"{min_v:.2f}"
            max_str = int(max_v) if max_v.is_integer() else f"{max_v:.2f}"
            avg_str = int(avg_v) if avg_v.is_integer() else f"{avg_v:.2f}"
            sum_str = int(sum_v) if sum_v.is_integer() else f"{sum_v:.2f}"
            stats_lines.append(
                f"- Column '{col}': Minimum = {min_str}, Maximum = {max_str}, Average = {avg_str}, Total Sum = {sum_str}, Count = {len(nums)}"
            )
        else:
            unique_vals = list(dict.fromkeys(values))[:8]
            stats_lines.append(
                f"- Column '{col}': {len(values)} entries, Unique sample: {', '.join(unique_vals[:5])}"
            )

    pages = []
    # Page 1: Overview and Statistical Summary
    overview_text = (
        f"CSV Document Overview: '{file_path.name}'\n"
        f"Total Records: {total_records}\n"
        f"Total Columns: {len(header)}\n"
        f"Columns: {', '.join(header)}\n\n"
        f"Summary & Column Statistics:\n"
        + "\n".join(stats_lines)
    )
    pages.append({
        "text": overview_text,
        "metadata": {
            "source": file_path.name,
            "page": 1
        }
    })

    # Subsequent pages: batches of rows (25 rows per page)
    batch_size = 25
    page_num = 2
    for i in range(0, total_records, batch_size):
        batch = data_rows[i : i + batch_size]
        row_lines = []
        for row_idx, r in enumerate(batch, start=i + 1):
            parts = []
            for col_idx, h in enumerate(header):
                val = r[col_idx].strip() if col_idx < len(r) else ""
                parts.append(f"{h}: {val}")
            row_lines.append(f"Row {row_idx}: " + " | ".join(parts))

        page_text = f"Records (Rows {i+1} to {min(i+batch_size, total_records)} of {total_records}):\n\n" + "\n".join(row_lines)
        pages.append({
            "text": page_text,
            "metadata": {
                "source": file_path.name,
                "page": page_num
            }
        })
        page_num += 1

    return pages


# ============================================================
# XLSX EXTRACTOR
# ============================================================

def _extract_xlsx(file_path: Path) -> List[Dict[str, Any]]:
    """Extracts Excel sheets with statistics and row records."""
    file_path = Path(file_path)

    # 1. Try openpyxl
    try:
        import openpyxl
        wb = openpyxl.load_workbook(str(file_path), data_only=True, read_only=True)
        pages = []
        page_num = 1
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            all_rows = []
            for r in ws.iter_rows(values_only=True):
                if any(cell is not None and str(cell).strip() != "" for cell in r):
                    all_rows.append([str(c).strip() if c is not None else "" for c in r])

            if all_rows:
                sheet_pages = _format_tabular_data(all_rows, file_path.name, sheet_name=sheet_name, start_page=page_num)
                pages.extend(sheet_pages)
                page_num += len(sheet_pages)
        wb.close()
        if pages:
            return pages
    except Exception:
        pass

    # 2. Try pandas
    try:
        import pandas as pd
        excel_file = pd.ExcelFile(str(file_path))
        pages = []
        page_num = 1
        for sheet_name in excel_file.sheet_names:
            df = excel_file.parse(sheet_name)
            if not df.empty:
                headers = [str(c) for c in df.columns]
                rows = [headers] + [[str(v) if pd.notna(v) else "" for v in row] for row in df.values]
                sheet_pages = _format_tabular_data(rows, file_path.name, sheet_name=sheet_name, start_page=page_num)
                pages.extend(sheet_pages)
                page_num += len(sheet_pages)
        if pages:
            return pages
    except Exception:
        pass

    # 3. Pure Python fallback: zipfile + XML on xl/worksheets/sheet*.xml and xl/sharedStrings.xml
    try:
        with zipfile.ZipFile(str(file_path), "r") as z:
            # Read shared strings
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                ss_tree = ET.fromstring(z.read("xl/sharedStrings.xml"))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                for si in ss_tree.iter(f"{{{ns['x']}}}si"):
                    t_nodes = [t.text for t in si.iter(f"{{{ns['x']}}}t") if t.text]
                    shared_strings.append("".join(t_nodes))

            # Find sheets
            sheet_files = sorted([f for f in z.namelist() if f.startswith("xl/worksheets/sheet") and f.endswith(".xml")])
            pages = []
            page_num = 1
            for sheet_idx, sheet_file in enumerate(sheet_files, start=1):
                s_tree = ET.fromstring(z.read(sheet_file))
                ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                all_rows = []
                for row_elem in s_tree.iter(f"{{{ns['x']}}}row"):
                    row_vals = []
                    for c in row_elem.iter(f"{{{ns['x']}}}c"):
                        c_type = c.attrib.get("t")
                        v_elem = c.find(f"{{{ns['x']}}}v")
                        val = ""
                        if v_elem is not None and v_elem.text:
                            raw_val = v_elem.text
                            if c_type == "s" and raw_val.isdigit():
                                idx = int(raw_val)
                                val = shared_strings[idx] if idx < len(shared_strings) else raw_val
                            else:
                                val = raw_val
                        row_vals.append(val)
                    if any(row_vals):
                        all_rows.append(row_vals)

                if all_rows:
                    sheet_pages = _format_tabular_data(
                        all_rows,
                        file_path.name,
                        sheet_name=f"Sheet {sheet_idx}",
                        start_page=page_num
                    )
                    pages.extend(sheet_pages)
                    page_num += len(sheet_pages)

            if pages:
                return pages
    except Exception:
        pass

    return _extract_txt(file_path)


def _format_tabular_data(rows: List[List[str]], source_name: str, sheet_name: str = "Sheet1", start_page: int = 1) -> List[Dict[str, Any]]:
    if not rows:
        return []
    header = rows[0]
    data_rows = rows[1:] if len(rows) > 1 else []
    total_records = len(data_rows)

    col_data: Dict[str, List[str]] = {col: [] for col in header}
    for row in data_rows:
        for idx, col in enumerate(header):
            val = row[idx].strip() if idx < len(row) else ""
            if val:
                col_data[col].append(val)

    stats_lines = []
    for col, values in col_data.items():
        if not values:
            continue
        nums = []
        for v in values:
            try:
                nums.append(float(v.replace(",", "").replace("$", "").replace("%", "")))
            except ValueError:
                pass

        if nums and len(nums) >= max(1, len(values) * 0.7):
            min_v = min(nums)
            max_v = max(nums)
            avg_v = sum(nums) / len(nums)
            sum_v = sum(nums)
            min_str = int(min_v) if min_v.is_integer() else f"{min_v:.2f}"
            max_str = int(max_v) if max_v.is_integer() else f"{max_v:.2f}"
            avg_str = int(avg_v) if avg_v.is_integer() else f"{avg_v:.2f}"
            sum_str = int(sum_v) if sum_v.is_integer() else f"{sum_v:.2f}"
            stats_lines.append(
                f"- Column '{col}': Minimum = {min_str}, Maximum = {max_str}, Average = {avg_str}, Total Sum = {sum_str}, Count = {len(nums)}"
            )
        else:
            unique_vals = list(dict.fromkeys(values))[:8]
            stats_lines.append(
                f"- Column '{col}': {len(values)} entries, Unique sample: {', '.join(unique_vals[:5])}"
            )

    pages = []
    overview_text = (
        f"Spreadsheet Sheet: '{sheet_name}' in '{source_name}'\n"
        f"Total Records: {total_records}\n"
        f"Total Columns: {len(header)}\n"
        f"Columns: {', '.join(header)}\n\n"
        f"Summary & Column Statistics:\n"
        + "\n".join(stats_lines)
    )
    pages.append({
        "text": overview_text,
        "metadata": {
            "source": source_name,
            "page": start_page,
            "sheet": sheet_name
        }
    })

    batch_size = 25
    current_page = start_page + 1
    for i in range(0, total_records, batch_size):
        batch = data_rows[i : i + batch_size]
        row_lines = []
        for row_idx, r in enumerate(batch, start=i + 1):
            parts = []
            for col_idx, h in enumerate(header):
                val = r[col_idx].strip() if col_idx < len(r) else ""
                parts.append(f"{h}: {val}")
            row_lines.append(f"Row {row_idx}: " + " | ".join(parts))

        page_text = (
            f"Spreadsheet '{sheet_name}' Data (Rows {i+1} to {min(i+batch_size, total_records)} of {total_records}):\n\n"
            + "\n".join(row_lines)
        )
        pages.append({
            "text": page_text,
            "metadata": {
                "source": source_name,
                "page": current_page,
                "sheet": sheet_name
            }
        })
        current_page += 1

    return pages


# ============================================================
# PPTX EXTRACTOR
# ============================================================

def _extract_pptx(file_path: Path) -> List[Dict[str, Any]]:
    """Extracts text per slide from PowerPoint presentations."""
    file_path = Path(file_path)

    # 1. Try python-pptx
    try:
        import pptx
        prs = pptx.Presentation(str(file_path))
        pages = []
        for slide_idx, slide in enumerate(prs.slides, start=1):
            slide_texts = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        t = para.text.strip()
                        if t:
                            slide_texts.append(t)
            if slide_texts:
                pages.append({
                    "text": f"--- Slide {slide_idx} ---\n" + "\n".join(slide_texts),
                    "metadata": {
                        "source": file_path.name,
                        "page": slide_idx
                    }
                })
        if pages:
            return pages
    except Exception:
        pass

    # 2. Pure Python fallback via zipfile + XML on ppt/slides/slide*.xml
    try:
        with zipfile.ZipFile(str(file_path), "r") as z:
            slide_files = [f for f in z.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")]
            def _get_slide_num(s):
                m = re.search(r"slide(\d+)\.xml", s)
                return int(m.group(1)) if m else 0
            slide_files = sorted(slide_files, key=_get_slide_num)

            pages = []
            for idx, sfile in enumerate(slide_files, start=1):
                tree = ET.fromstring(z.read(sfile))
                ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
                texts = [node.text for node in tree.iter(f"{{{ns['a']}}}t") if node.text]
                if texts:
                    clean_text = "\n".join([t.strip() for t in texts if t.strip()])
                    pages.append({
                        "text": f"--- Slide {idx} ---\n{clean_text}",
                        "metadata": {
                            "source": file_path.name,
                            "page": idx
                        }
                    })
            if pages:
                return pages
    except Exception:
        pass

    return _extract_txt(file_path)


# ============================================================
# PLAIN TEXT EXTRACTOR
# ============================================================

def _extract_txt(file_path: Path) -> List[Dict[str, Any]]:
    file_path = Path(file_path)
    content = ""
    for enc in ("utf-8", "latin1", "cp1252"):
        try:
            content = file_path.read_text(encoding=enc)
            break
        except Exception:
            continue

    if not content:
        return []

    paras = [p.strip() for p in content.split("\n\n") if p.strip()]
    if not paras:
        paras = [content.strip()]
    return _paginate_paragraphs(paras, file_path.name, words_per_page=500)


# ============================================================
# UNIVERSAL LOADER
# ============================================================

def load_document(file_path: Path) -> List[Dict[str, Any]]:
    """
    Universal document entry point.
    Returns:
    [{"text": "...", "metadata": {"source": "...", "page": 1}}]
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _load_pdf_entry(path)

    elif suffix in (".docx", ".doc"):
        return _extract_docx(path)

    elif suffix == ".csv":
        return _extract_csv(path)

    elif suffix in (".xlsx", ".xls"):
        return _extract_xlsx(path)

    elif suffix in (".pptx", ".ppt"):
        return _extract_pptx(path)

    elif suffix in (".txt", ".md", ".text", ".log"):
        return _extract_txt(path)

    # Generic fallback
    return _extract_txt(path)
