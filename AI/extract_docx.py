"""Extract readable text (paragraphs + tables) from a .docx into a .txt file.

Stdlib only - no python-docx needed.

Usage:
    python extract_docx.py "C:\\path\\to\\file.docx" [out.txt]
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def paragraph_text(p: ET.Element) -> str:
    parts = []
    for node in p.iter():
        if node.tag == W + "t":
            parts.append(node.text or "")
        elif node.tag == W + "tab":
            parts.append("\t")
        elif node.tag == W + "br":
            parts.append("\n")
    return "".join(parts)


def table_rows(tbl: ET.Element) -> list[list[str]]:
    rows = []
    for tr in tbl.iter(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            text = " ".join(
                paragraph_text(p).strip() for p in tc.findall(W + "p")
            ).strip()
            cells.append(text)
        rows.append(cells)
    return rows


def extract(docx_path: Path) -> str:
    with zipfile.ZipFile(docx_path) as zf:
        xml = zf.read("word/document.xml")

    root = ET.fromstring(xml)
    body = root.find(W + "body")
    if body is None:
        return ""

    out: list[str] = []
    for child in body:
        if child.tag == W + "p":
            text = paragraph_text(child)
            if text.strip():
                out.append(text.rstrip())
        elif child.tag == W + "tbl":
            rows = table_rows(child)
            if not rows:
                continue
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            out.append("")
            for i, row in enumerate(rows):
                out.append("| " + " | ".join(c.strip() for c in row) + " |")
                if i == 0:
                    out.append("|" + "---|" * width)
            out.append("")
    return "\n".join(out)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    docx_path = Path(sys.argv[1]).expanduser().resolve()
    if not docx_path.exists():
        print(f"ERROR: not found: {docx_path}")
        return 1

    out_path = (
        Path(sys.argv[2]).expanduser().resolve()
        if len(sys.argv) > 2
        else docx_path.with_suffix(".txt")
    )

    text = extract(docx_path)
    text = re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"
    out_path.write_text(text, encoding="utf-8")

    print(f"Wrote {len(text):,} characters to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
