#!/usr/bin/env python3
"""Stage 1: Extract text from a book PDF, segmented by chapter.

Also extracts embedded images and tracks page ranges per chapter.
"""

import sys
import json
import re
import os
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


def extract_images(pdf_path: str, output_dir: str, min_size: int = 20000) -> list[dict]:
    """Extract unique images from PDF pages. Deduplicates by content hash."""
    import hashlib
    images_dir = os.path.join(output_dir, "images")
    os.makedirs(images_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    extracted = []
    img_counter = 0
    seen_hashes = set()  # Deduplicate identical images
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image is None:
                    continue
                
                image_bytes = base_image["image"]
                # Skip tiny images (icons, bullets, etc.)
                if len(image_bytes) < min_size:
                    continue
                
                # Deduplicate by content hash
                img_hash = hashlib.md5(image_bytes).hexdigest()
                if img_hash in seen_hashes:
                    continue
                seen_hashes.add(img_hash)
                
                ext = base_image.get("ext", "png")
                width = base_image.get("width", 0)
                height = base_image.get("height", 0)
                
                # Skip very small dimensions (likely decorative)
                if width < 150 or height < 150:
                    continue
                
                img_counter += 1
                filename = f"page{page_num + 1:03d}_img{img_counter:02d}.{ext}"
                filepath = os.path.join(images_dir, filename)
                
                with open(filepath, 'wb') as f:
                    f.write(image_bytes)
                
                extracted.append({
                    "filename": filename,
                    "page_num": page_num + 1,
                    "width": width,
                    "height": height,
                    "size_bytes": len(image_bytes),
                    "caption": ""
                })
            except Exception:
                continue
    
    doc.close()
    return extracted


def detect_chapters(pages: list[dict]) -> list[dict]:
    """Detect chapter boundaries. Returns chapters with page ranges."""
    chapter_patterns = [
        r'^(?:Chapter|CHAPTER)\s+(\d+)',
        r'^(\d+)\s*\n',
        r'^Part\s+([IVXLC]+)',
        r'^PART\s+([IVXLC]+)',
    ]
    
    chapters = []
    current_chapter = {
        "chapter_num": 0,
        "title": "Front Matter",
        "pages": [],
        "start_page": 1,
        "end_page": 1,
        "text": ""
    }
    
    for page in pages:
        text = page["text"]
        found_chapter = False
        
        for pattern in chapter_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match and page["page_num"] > 5:
                if current_chapter["pages"]:
                    current_chapter["text"] = "\n\n".join(
                        p["text"] for p in current_chapter["pages"]
                    )
                    current_chapter["start_page"] = current_chapter["pages"][0]["page_num"]
                    current_chapter["end_page"] = current_chapter["pages"][-1]["page_num"]
                    chapters.append(current_chapter)
                
                lines = text.split('\n')
                title_lines = [l.strip() for l in lines[:5] if l.strip()]
                title = " ".join(title_lines[:2])
                
                current_chapter = {
                    "chapter_num": len(chapters) + 1,
                    "title": title,
                    "pages": [page],
                    "start_page": page["page_num"],
                    "end_page": page["page_num"],
                    "text": ""
                }
                found_chapter = True
                break
        
        if not found_chapter:
            current_chapter["pages"].append(page)
    
    if current_chapter["pages"]:
        current_chapter["text"] = "\n\n".join(
            p["text"] for p in current_chapter["pages"]
        )
        current_chapter["start_page"] = current_chapter["pages"][0]["page_num"]
        current_chapter["end_page"] = current_chapter["pages"][-1]["page_num"]
        chapters.append(current_chapter)
    
    return chapters


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_pdf.py <pdf_path> [output_path]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "chapters_raw.json"
    output_dir = os.path.dirname(os.path.abspath(output_path))
    
    print(f"📄 Extracting text from: {pdf_path}")
    pages = extract_text_from_pdf(pdf_path)
    print(f"   Found {len(pages)} pages with text")
    
    # Extract images
    print(f"🖼️  Extracting images...")
    images = extract_images(pdf_path, output_dir)
    print(f"   Found {len(images)} significant images/diagrams")
    
    # Full text for LLM
    full_text = "\n\n---PAGE BREAK---\n\n".join(p["text"] for p in pages)
    
    # Detect chapters
    chapters = detect_chapters(pages)
    print(f"   Detected {len(chapters)} chapter segments")
    
    for ch in chapters:
        word_count = len(ch["text"].split())
        print(f"   Ch {ch['chapter_num']}: pp.{ch['start_page']}-{ch['end_page']} | {ch['title'][:50]}... ({word_count} words)")
        del ch["pages"]
    
    # Map images to chapters
    for img in images:
        for ch in chapters:
            if ch["start_page"] <= img["page_num"] <= ch["end_page"]:
                img["chapter_num"] = ch["chapter_num"]
                break
    
    output = {
        "source": pdf_path,
        "total_pages": len(pages),
        "chapters": chapters,
        "images": images,
        "full_text": full_text
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Saved to {output_path}")
    print(f"   Total text: {len(full_text):,} characters, {len(full_text.split()):,} words")
    print(f"   Images: {len(images)} extracted to {os.path.join(output_dir, 'images')}/")


if __name__ == "__main__":
    main()
