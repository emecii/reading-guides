#!/usr/bin/env python3
"""Stage 2: Analyze extracted book text with Gemini to produce structured book.json.

Uses a 2-pass approach to avoid output token truncation:
  Pass 1 → meta, books, concepts, scenarios, flashcards, quizQuestions
  Pass 2 → chapters_detail
"""

import sys
import json
import os
import time
import google.generativeai as genai


def get_model():
    """Initialize Gemini model using .env file or environment variable."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ[key.strip()] = val.strip()

    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ No Gemini API key found. Create a .env file with GOOGLE_API_KEY=your-key")
        sys.exit(1)

    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-2.5-flash")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PASS1_PROMPT = """Analyze this book text and produce a JSON with these fields.
Do NOT include "chapters_detail" — that will be a separate request.

{
  "meta": {
    "slug": "url-friendly-slug",
    "title": "Book Title",
    "author": "Author Name",
    "language": "en",
    "description": "2-3 sentence book description",
    "hero_subtitle": "SHORT UPPERCASE TAGLINE",
    "hero_emphasis_word": "one key word from title to emphasize"
  },
  "books": [
    {
      "num": "I",
      "title": "Part/Section Title",
      "desc": "2-3 sentence part description",
      "chapters": [
        {
          "num": 1,
          "title": "Chapter Title",
          "oneliner": "One-sentence summary",
          "summary": "2-3 sentence detailed summary",
          "ideas": ["Key Idea 1", "Key Idea 2", "Key Idea 3"],
          "priority": "must-read or optional"
        }
      ]
    }
  ],
  "concepts": [
    {
      "id": "url-slug",
      "name": "Concept Name",
      "badge": "core|strategy|risk|math|meta",
      "short": "2-sentence description",
      "example": "Concrete example",
      "detail": "Full paragraph (4-6 sentences)",
      "quote": "Relevant quote from the book",
      "related": ["other-concept-id"]
    }
  ],
  "scenarios": [
    {
      "text": "Real-world scenario",
      "context": "Context hint",
      "answer": "concept-id",
      "explanation": "Why (2-3 sentences)"
    }
  ],
  "flashcards": [
    {
      "category": "Topic",
      "q": "Question",
      "a": "Answer (can use <strong> for emphasis)"
    }
  ],
  "quizQuestions": [
    {
      "q": "Deep-understanding question",
      "options": ["A", "B", "C", "D"],
      "correct": 0,
      "explanation": "Why correct (2-3 sentences)"
    }
  ]
}

Generate 10-15 concepts, 10-16 scenarios, 16+ flashcards, 10 quiz questions.
Scenario "answer" must match a concept id from your concepts array.

BOOK TEXT:

"""

PASS2_PROMPT = """Based on this book text, generate chapter-by-chapter analysis.
Return JSON: {"chapters_detail": [...]}

Each chapter object:
{
  "num": 1,
  "book_label": "Part I · Title",
  "title": "Chapter Title",
  "subtitle": "One-liner",
  "word_count": "~N words",
  "reading_time": "N min",
  "epigraph": {"text": "Quote", "attribution": "Author"},
  "argument_flow": [{"heading": "Title", "body": "2-3 sentences"}],
  "sections": [{"label": "A", "title": "Title", "paragraphs": ["p1","p2"]}],
  "examples": [{"icon": "emoji", "title": "T", "desc": "D", "lesson": "L"}],
  "quotes": [{"text": "Quote", "context": "Context"}],
  "concept_links": ["concept-id"],
  "reflections": ["Question 1","Question 2","Question 3","Question 4"],
  "prev_chapter": null,
  "next_chapter": {"num": 2, "title": "Title"}
}

Per chapter: 4-6 argument steps, 2-3 sections (2-3 paragraphs each), 3-5 examples, 3-5 quotes, 4 reflections.
prev_chapter=null for ch1, next_chapter=null for last chapter.

BOOK TEXT:

"""


# ---------------------------------------------------------------------------
# JSON repair for truncated output
# ---------------------------------------------------------------------------

def repair_json(text):
    """Fix truncated JSON by closing open brackets."""
    stack = []
    last_valid = 0
    in_string = False
    escape = False

    for i, ch in enumerate(text):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
            last_valid = i + 1
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()
            last_valid = i + 1

    if not stack:
        return text

    result = text[:last_valid].rstrip().rstrip(',')
    for bracket in reversed(stack):
        result += '}' if bracket == '{' else ']'
    return result


# ---------------------------------------------------------------------------
# Gemini caller with retry
# ---------------------------------------------------------------------------

def call_gemini(prompt, model, label=""):
    """Call Gemini with retry logic for rate limits."""
    max_retries = 3
    base_delay = 30

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                delay = base_delay * (2 ** (attempt - 1))
                print(f"   ⏳ Rate limited. Waiting {delay}s before retry {attempt}/{max_retries}...")
                time.sleep(delay)

            print(f"   🤖 {label} (attempt {attempt + 1})...")

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                    max_output_tokens=65536,
                ),
            )

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]

            # Save raw for debugging
            safe_label = label.replace(' ', '_').lower()
            debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"raw_{safe_label}.json")
            with open(debug_path, 'w', encoding='utf-8') as df:
                df.write(text)

            try:
                return json.loads(text)
            except json.JSONDecodeError as je:
                print(f"   ⚠️  JSON truncated at char {je.pos}/{len(text)}, repairing...")
                repaired = repair_json(text)
                return json.loads(repaired)

        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "rate" in err.lower():
                if attempt < max_retries:
                    continue
                print(f"   ❌ Rate limit exceeded after {max_retries} retries.")
            else:
                print(f"   ❌ Error: {e}")
            raise


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_book.py <chapters_raw.json> [output_book.json]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else "book.json"

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    full_text = data["full_text"]
    print(f"📚 Loaded {len(full_text):,} characters of book text")

    model = get_model()

    # --- Pass 1: Structure + study materials ---
    print("\n══ Pass 1: Book structure, concepts & study materials ══")
    pass1 = call_gemini(PASS1_PROMPT + full_text, model, label="pass1")
    print(f"   ✓ {len(pass1.get('books',[]))} parts, {len(pass1.get('concepts',[]))} concepts")
    print(f"   ✓ {len(pass1.get('flashcards',[]))} flashcards, {len(pass1.get('quizQuestions',[]))} quiz")
    print(f"   ✓ {len(pass1.get('scenarios',[]))} scenarios")

    # Pause between passes to respect rate limits
    print("\n   ⏳ Pausing 15s before Pass 2...")
    time.sleep(15)

    # --- Pass 2: Chapter details ---
    print("\n══ Pass 2: Detailed chapter analysis ══")
    pass2 = call_gemini(PASS2_PROMPT + full_text, model, label="pass2")
    chapters = pass2.get("chapters_detail", [])
    print(f"   ✓ {len(chapters)} chapter details generated")

    # --- Merge & save ---
    book_data = {**pass1, "chapters_detail": chapters}

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(book_data, f, ensure_ascii=False, indent=2)

    meta = book_data.get("meta", {})
    print(f"\n✅ Analysis complete: {meta.get('title', 'Unknown')}")
    print(f"   Author:     {meta.get('author', 'Unknown')}")
    print(f"   Parts:      {len(book_data.get('books', []))}")
    print(f"   Chapters:   {len(chapters)}")
    print(f"   Concepts:   {len(book_data.get('concepts', []))}")
    print(f"   Scenarios:  {len(book_data.get('scenarios', []))}")
    print(f"   Flashcards: {len(book_data.get('flashcards', []))}")
    print(f"   Quiz:       {len(book_data.get('quizQuestions', []))}")
    print(f"   Saved to:   {output_path}")


if __name__ == "__main__":
    main()
