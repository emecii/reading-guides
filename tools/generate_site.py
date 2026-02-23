#!/usr/bin/env python3
"""Stage 3: Generate HTML site from book.json using Jinja2 templates."""

import sys
import json
import os
import shutil
from jinja2 import Environment, FileSystemLoader


def load_book_data(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_site(book_data: dict, output_dir: str, templates_dir: str):
    """Generate the full book site from structured data."""
    meta = book_data["meta"]
    slug = meta["slug"]
    book_dir = os.path.join(output_dir, "books", slug)
    chapters_dir = os.path.join(book_dir, "chapters")
    css_dir = os.path.join(book_dir, "css")
    
    # Create directories
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(css_dir, exist_ok=True)
    
    # Set up Jinja2
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    # Generate book index page
    print(f"📄 Generating book index: books/{slug}/index.html")
    template = env.get_template("book_index.html.j2")
    html = template.render(
        meta=meta,
        books=book_data["books"],
        concepts=book_data["concepts"],
        scenarios=book_data["scenarios"],
        flashcards=book_data["flashcards"],
        quiz_questions=book_data["quizQuestions"],
        concepts_json=json.dumps(book_data["concepts"], ensure_ascii=False),
        books_json=json.dumps(book_data["books"], ensure_ascii=False),
        scenarios_json=json.dumps(book_data["scenarios"], ensure_ascii=False),
        flashcards_json=json.dumps(book_data["flashcards"], ensure_ascii=False),
        quiz_json=json.dumps(book_data["quizQuestions"], ensure_ascii=False),
    )
    with open(os.path.join(book_dir, "index.html"), 'w', encoding='utf-8') as f:
        f.write(html)
    
    # Generate chapter pages
    chapter_template = env.get_template("chapter.html.j2")
    for ch in book_data["chapters_detail"]:
        ch_num = str(ch["num"]).zfill(2)
        filename = f"ch{ch_num}.html"
        print(f"   📄 Chapter {ch['num']}: {ch['title'][:50]}...")
        
        html = chapter_template.render(
            meta=meta,
            chapter=ch,
        )
        with open(os.path.join(chapters_dir, filename), 'w', encoding='utf-8') as f:
            f.write(html)
    
    # Copy/generate chapter.css (reuse from antifragile or generate minimal)
    antifragile_css = os.path.join(output_dir, "books", "antifragile", "css", "chapter.css")
    if os.path.exists(antifragile_css):
        shutil.copy2(antifragile_css, os.path.join(css_dir, "chapter.css"))
        print(f"   📋 Copied chapter.css from antifragile")
    
    # Copy extracted images
    tools_images = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
    if os.path.exists(tools_images):
        images_dir = os.path.join(book_dir, "images")
        if os.path.exists(images_dir):
            shutil.rmtree(images_dir)
        shutil.copytree(tools_images, images_dir)
        img_count = len([f for f in os.listdir(images_dir) if not f.startswith('.')])
        print(f"   🖼️  Copied {img_count} images to books/{slug}/images/")
    
    print(f"\n✅ Site generated at: books/{slug}/")
    print(f"   Index: books/{slug}/index.html")
    print(f"   Chapters: {len(book_data['chapters_detail'])} files")


def update_catalog(book_data: dict, output_dir: str):
    """Add the new book to the root index.html catalog."""
    meta = book_data["meta"]
    catalog_path = os.path.join(output_dir, "index.html")
    
    if not os.path.exists(catalog_path):
        print("   ⚠️  No root index.html found, skipping catalog update")
        return
    
    with open(catalog_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already added
    if meta["slug"] in content:
        print(f"   📋 Book already in catalog")
        return
    
    # Count chapters
    total_chapters = sum(len(b["chapters"]) for b in book_data["books"])
    total_parts = len(book_data["books"])
    
    new_entry = f"""
        <!-- {meta['title']} -->
        <a href="books/{meta['slug']}/index.html" class="book-entry" id="book-{meta['slug']}">
          <div class="book-entry-lang">{meta['language'].upper()}</div>
          <div class="book-entry-title">{meta['title']}</div>
          <div class="book-entry-author">{meta['author']}</div>
          <div class="book-entry-desc">
            {meta['description']}
          </div>
          <div class="book-entry-stats">
            <div class="book-stat"><span class="book-stat-num">{total_chapters}</span> chapters</div>
            <div class="book-stat"><span class="book-stat-num">{total_parts}</span> parts</div>
            <div class="book-stat"><span class="book-stat-num">{len(book_data['concepts'])}</span> concepts</div>
          </div>
          <div class="book-entry-arrow">→</div>
        </a>
"""
    
    # Insert before the placeholder card
    placeholder = '<!-- Placeholder for next book -->'
    if placeholder in content:
        content = content.replace(placeholder, new_entry + "\n        " + placeholder)
        with open(catalog_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✅ Added {meta['title']} to catalog")
    else:
        print(f"   ⚠️  Could not find placeholder in catalog, manual update needed")


def main():
    if len(sys.argv) < 2:
        print("Usage: python generate_site.py <book.json> [output_dir]")
        sys.exit(1)
    
    book_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    
    print(f"🔧 Loading book data from: {book_path}")
    book_data = load_book_data(book_path)
    
    print(f"🏗️  Generating site in: {output_dir}")
    generate_site(book_data, output_dir, templates_dir)
    
    print(f"\n📚 Updating catalog...")
    update_catalog(book_data, output_dir)


if __name__ == "__main__":
    main()
