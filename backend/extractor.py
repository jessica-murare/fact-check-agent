import fitz  # PyMuPDF


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF given its raw bytes.
    Returns a single string with page separators.
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        if text.strip():
            pages.append(f"--- Page {page_num} ---\n{text.strip()}")

    doc.close()

    if not pages:
        raise ValueError("No extractable text found in PDF. It may be a scanned image-only PDF.")

    return "\n\n".join(pages)