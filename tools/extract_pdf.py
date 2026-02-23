#!/usr/bin/env python3
"""Stage 1: Extract text from a book PDF, segmented by chapter."""

import sys
import json
import re
import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """Extract all text from PDF, page by page."""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        if text.strip():
            pages.append({
                "page_num": i + 1,
                "text": text.strip()
            })
    doc.close()
    return pages


def detect_chapters(pages: list[dict]) -> list[dict]:
    """
    Attempt to detect chapter boundaries using common patterns.
    Returns a list of chapters with their text content.
    """
    # Common chapter heading patterns
    chapter_patterns = [
        r'^(?:Chapter|CHAPTER)\s+(\d+)',
        r'^(\d+)\s*\n',  # Just a number at the start of a page
        r'^Part\s+([IVXLC]+)',
        r'^PART\s+([IVXLC]+)',
    ]
    
    chapters = []
    current_chapter = {
        "chapter_num": 0,
        "title": "Front Matter",
        "pages": [],
        "text": ""
    }
    
    for page in pages:
        text = page["text"]
        found_chapter = False
        
        for pattern in chapter_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match and page["page_num"] > 5:  # Skip first pages (cover, TOC)
                # Save previous chapter
                if current_chapter["pages"]:
                    current_chapter["text"] = "\n\n".join(
                        p["text"] for p in current_chapter["pages"]
                    )
                    chapters.append(current_chapter)
                
                # Extract title from the heading area
                lines = text.split('\n')
                title_lines = [l.strip() for l in lines[:5] if l.strip()]
                title = " ".join(title_lines[:2])
                
                current_chapter = {
                    "chapter_num": len(chapters) + 1,
                    "title": title,
                    "pages": [page],
                    "text": ""
                }
                found_chapter = True
                break
        
        if not found_chapter:
            current_chapter["pages"].append(page)
    
    # Don't forget the last chapter
    if current_chapter["pages"]:
        current_chapter["text"] = "\n\n".join(
            p["text"] for p in current_chapter["pages"]
        )
        chapters.append(current_chapter)
    
    return chapters


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_path> [output_path]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "chapters_raw.json"
    
    print(f"📄 Extracting text from: {pdf_path}")
    pages = extract_text_from_pdf(pdf_path)
    print(f"   Found {len(pages)} pages with text")
    
    # Also save the full text for LLM processing
    full_text = "\n\n---PAGE BREAK---\n\n".join(p["text"] for p in pages)
    
    # Try to detect chapters
    chapters = detect_chapters(pages)
    print(f"   Detected {len(chapters)} chapter segments")
    
    for ch in chapters:
        word_count = len(ch["text"].split())
        print(f"   Ch {ch['chapter_num']}: {ch['title'][:60]}... ({word_count} words)")
        # Remove pages list for cleaner JSON
        del ch["pages"]
    
    output = {
        "source": pdf_path,
        "total_pages": len(pages),
        "chapters": chapters,
        "full_text": full_text
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved to {output_path}")
    print(f"   Total text: {len(full_text)} characters, {len(full_text.split())} words")


if __name__ == "__main__":
    main()
