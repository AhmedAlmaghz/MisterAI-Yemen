#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script to parse Markdown curriculum files into structured JSON files.
Hierarchy: Book -> Unit -> Lesson -> Lesson Elements
Preserves full text, equations, tables, activities, exercises, and unit evaluations.
"""

import os
import sys
import re
import json
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

OUTPUT_DIR = r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\json_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Helper to clean titles
def clean_text(txt):
    if not txt:
        return ""
    # Remove leading hashes, emojis, asterisks, bullet markers
    cleaned = re.sub(r'^[#\s📘*]+', '', txt).strip()
    cleaned = re.sub(r'^\**|\**$', '', cleaned).strip()
    return cleaned

# Extract page number if present like (ص ١٢) or (ص 12)
def extract_page_number(txt):
    match = re.search(r'\(ص\s*([\d\u0660-\u0669]+)\)', txt)
    if match:
        return match.group(1)
    return None

def parse_structured_book(fpath, book_key, subject_name):
    if not os.path.exists(fpath):
        print(f"Skipping missing file: {fpath}")
        return None

    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()

    # Book title extraction
    book_title = f"كتاب {subject_name} - الصف الثالث الثانوي (اليمن)"
    for line in lines[:15]:
        if line.startswith("# ") and "الوحدة" not in line:
            book_title = clean_text(line)
            break

    units = []
    current_unit = None
    current_lesson = None
    current_element = None

    # Regex patterns
    unit_pattern = re.compile(r'^#\s*📘?\s*(الوحدة\s+[\u0600-\u06FF\d\s]+:\s*.*|الوحدة\s+.*)')
    lesson_pattern = re.compile(r'^##\s*(الدرس\s+[\d\u0660-\u0669]+:\s*.*|الدرس\s+.*)')
    objectives_pattern = re.compile(r'^##\s*أهداف الوحدة')
    eval_pattern = re.compile(r'^##\s*(ملحق\s+الوحدة.*تقويم|تقويم\s+الوحدة|أسئلة\s+الوحدة|تقويم\s+الوحدة.*)')
    element_pattern = re.compile(r'^###\s*(.*)')

    mode = None # "unit_intro", "objectives", "lesson", "unit_eval"

    def flush_element():
        nonlocal current_element, current_lesson
        if current_element and current_lesson:
            text_str = "\n".join(current_element["content"]).strip()
            if text_str: # only append if non-empty
                current_element["content"] = text_str
                current_lesson["elements"].append(current_element)
            current_element = None

    def flush_lesson():
        nonlocal current_lesson, current_unit
        if current_lesson and current_unit:
            flush_element()
            current_unit["lessons"].append(current_lesson)
            current_lesson = None

    def flush_unit():
        nonlocal current_unit, units
        if current_unit:
            flush_lesson()
            units.append(current_unit)
            current_unit = None

    for line in lines:
        stripped = line.strip()

        # Check Unit header (# 📘 الوحدة...)
        if unit_pattern.match(line) or (line.startswith("# ") and "الوحدة" in line):
            flush_unit()
            
            u_title = clean_text(line)
            p_num = extract_page_number(line)
            unit_idx = len(units) + 1
            
            current_unit = {
                "unit_id": f"unit_{unit_idx}",
                "unit_number": unit_idx,
                "unit_title": u_title,
                "page_number": p_num,
                "objectives": [],
                "lessons": [],
                "unit_evaluation": None
            }
            mode = "unit_intro"
            continue

        # Check Unit objectives (## أهداف الوحدة)
        if objectives_pattern.match(line):
            mode = "objectives"
            continue

        # Check Unit evaluation (## ملحق الوحدة... تقويم الوحدة)
        if eval_pattern.match(line) and current_unit:
            flush_lesson()
            mode = "unit_eval"
            p_num = extract_page_number(line)
            current_unit["unit_evaluation"] = {
                "title": clean_text(line),
                "page_number": p_num,
                "content": []
            }
            continue

        # Check Lesson header (## الدرس 1: ...)
        if lesson_pattern.match(line) and current_unit:
            flush_lesson()
            l_title = clean_text(line)
            p_num = extract_page_number(line)
            lesson_idx = len(current_unit["lessons"]) + 1
            
            current_lesson = {
                "lesson_id": f"lesson_{current_unit['unit_number']}_{lesson_idx}",
                "lesson_number": lesson_idx,
                "lesson_title": l_title,
                "page_number": p_num,
                "elements": [],
                "activities": [],
                "exercises": []
            }
            mode = "lesson"
            continue

        # Check Element / Sub-header (### المحور الأول...)
        if element_pattern.match(line) and current_lesson:
            flush_element()
            
            e_title = clean_text(line)
            e_type = "مفهوم/شرح"
            if "محور" in e_title or "المحور" in e_title:
                e_type = "محور رئيسي"
            elif "نشاط" in e_title or "تجربة" in e_title:
                e_type = "نشاط/تجربة عملية"
            elif "مثال" in e_title or "أمثلة" in e_title:
                e_type = "مثال محلول"
            elif "تمارين" in e_title or "أسئلة" in e_title or "تدريب" in e_title:
                e_type = "تمارين وتدريبات"
            elif "جدول" in e_title:
                e_type = "جدول بيانات"
            
            elem_idx = len(current_lesson["elements"]) + 1
            current_element = {
                "element_id": f"elem_{current_lesson['lesson_id']}_{elem_idx}",
                "title": e_title,
                "type": e_type,
                "content": []
            }
            continue

        # Append text line depending on state
        if mode == "objectives" and current_unit:
            if stripped and not stripped.startswith("---"):
                current_unit["objectives"].append(stripped)
        elif mode == "unit_eval" and current_unit and current_unit["unit_evaluation"]:
            current_unit["unit_evaluation"]["content"].append(line)
        elif mode == "lesson" and current_lesson:
            if current_element:
                current_element["content"].append(line)
            else:
                # Content right under lesson header before any H3
                if stripped:
                    elem_idx = len(current_lesson["elements"]) + 1
                    current_element = {
                        "element_id": f"elem_{current_lesson['lesson_id']}_{elem_idx}",
                        "title": "مقدمة الدرس",
                        "type": "مقدمة",
                        "content": [line]
                    }

    # Flush remaining items
    flush_unit()

    # Clean array content to joined strings
    for u in units:
        if u["unit_evaluation"]:
            u["unit_evaluation"]["content"] = "\n".join(u["unit_evaluation"]["content"]).strip()

    book_data = {
        "book_metadata": {
            "title": book_title,
            "subject": subject_name,
            "grade": "الصف الثالث الثانوي",
            "country": "اليمن",
            "source_file": os.path.basename(fpath),
            "total_units": len(units),
            "generated_at": str(date.today())
        },
        "units": units
    }

    out_file = os.path.join(OUTPUT_DIR, f"{book_key}.json")
    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(book_data, out_f, ensure_ascii=False, indent=2)

    print(f"Successfully converted {book_key} -> {out_file} (Units: {len(units)})")
    return book_data

def parse_adaptive_book(fpath, book_key, subject_name):
    """Fallback / adaptive parser for Math, English, Arabic Reading/Texts."""
    if not os.path.exists(fpath):
        print(f"Skipping missing file: {fpath}")
        return None

    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()
    book_title = f"كتاب {subject_name} - الصف الثالث الثانوي (اليمن)"
    for line in lines[:20]:
        if line.startswith("# ") and "الوحدة" not in line:
            book_title = clean_text(line)
            break

    units = []
    current_unit = None
    current_lesson = None
    current_element = None

    def flush_element():
        nonlocal current_element, current_lesson
        if current_element and current_lesson:
            text_str = "\n".join(current_element["content"]).strip()
            if text_str:
                current_element["content"] = text_str
                current_lesson["elements"].append(current_element)
            current_element = None

    def flush_lesson():
        nonlocal current_lesson, current_unit
        if current_lesson and current_unit:
            flush_element()
            current_unit["lessons"].append(current_lesson)
            current_lesson = None

    def flush_unit():
        nonlocal current_unit, units
        if current_unit:
            flush_lesson()
            units.append(current_unit)
            current_unit = None

    for line in lines:
        stripped = line.strip()

        # Check Unit header (# or ## with "الوحدة" or major title)
        is_unit_header = False
        if line.startswith("# ") and ("الوحدة" in line or "كتاب" in line or "الأدب" in line or "الرياضيات" in line or "ENGLISH" in line):
            is_unit_header = True
        elif line.startswith("## ") and "الوحدة" in line:
            is_unit_header = True

        if is_unit_header:
            flush_unit()
            unit_idx = len(units) + 1
            current_unit = {
                "unit_id": f"unit_{unit_idx}",
                "unit_number": unit_idx,
                "unit_title": clean_text(line),
                "page_number": extract_page_number(line),
                "objectives": [],
                "lessons": [],
                "unit_evaluation": None
            }
            continue

        # Check Lesson header (## or ###)
        is_lesson_header = line.startswith("## ") or (line.startswith("# ") and not is_unit_header)
        if is_lesson_header:
            if not current_unit:
                current_unit = {
                    "unit_id": "unit_1",
                    "unit_number": 1,
                    "unit_title": "محتويات الكتاب",
                    "page_number": None,
                    "objectives": [],
                    "lessons": [],
                    "unit_evaluation": None
                }

            flush_lesson()
            lesson_idx = len(current_unit["lessons"]) + 1
            current_lesson = {
                "lesson_id": f"lesson_{current_unit['unit_number']}_{lesson_idx}",
                "lesson_number": lesson_idx,
                "lesson_title": clean_text(line),
                "page_number": extract_page_number(line),
                "elements": [],
                "activities": [],
                "exercises": []
            }
            continue

        # Check Element header (### or ####)
        if line.startswith("### ") or line.startswith("#### "):
            if current_lesson:
                flush_element()
                elem_idx = len(current_lesson["elements"]) + 1
                e_title = clean_text(line)
                e_type = "تمارين/مسائل" if "تمارين" in e_title or "أسئلة" in e_title else "مفهوم/شرح"
                current_element = {
                    "element_id": f"elem_{current_lesson['lesson_id']}_{elem_idx}",
                    "title": e_title,
                    "type": e_type,
                    "content": []
                }
                continue

        # Append content line
        if current_lesson:
            if not current_element:
                if stripped:
                    elem_idx = len(current_lesson["elements"]) + 1
                    current_element = {
                        "element_id": f"elem_{current_lesson['lesson_id']}_{elem_idx}",
                        "title": "المحتوى الرئيسي",
                        "type": "شرح/مضمون",
                        "content": [line]
                    }
            else:
                current_element["content"].append(line)

    # Flush remaining
    flush_unit()

    # Clean array content
    for u in units:
        if u["unit_evaluation"]:
            u["unit_evaluation"]["content"] = "\n".join(u["unit_evaluation"]["content"]).strip()

    book_data = {
        "book_metadata": {
            "title": book_title,
            "subject": subject_name,
            "grade": "الصف الثالث الثانوي",
            "country": "اليمن",
            "source_file": os.path.basename(fpath),
            "total_units": len(units),
            "generated_at": str(date.today())
        },
        "units": units
    }

    out_file = os.path.join(OUTPUT_DIR, f"{book_key}.json")
    with open(out_file, "w", encoding="utf-8") as out_f:
        json.dump(book_data, out_f, ensure_ascii=False, indent=2)

    print(f"Successfully converted {book_key} -> {out_file} (Units: {len(units)})")
    return book_data


def main():
    books_to_process = [
        # Structured curriculum books
        ("chemistry_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\الكل\yemen-12th-chimstry.md", "الكيمياء", True),
        ("physics_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\الكل\yemen-12th-pysices.md", "الفيزياء", True),
        ("biology_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\الكل\yemen-12th-pilogy.md", "الأحياء وعلم الأرض", True),
        # Adaptive curriculum books
        ("math_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\رياضيات\mathematic_12th\markdown.md", "الرياضيات", False),
        ("english_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\الانجليزي\english_12th\markdown.md", "اللغة الإنجليزية", False),
        ("arabic_reading_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\قراءة وبلاغة ونصوص\reading_12th\markdown-reading.md", "القراءة والبلاغة", False),
        ("arabic_texts_12th", r"f:\Mister_ai_Yemen\MisterAI-Yemen\Docs\قراءة وبلاغة ونصوص\nosos_12th\markdown.md", "الأدب والنصوص", False),
    ]

    summary = []

    for key, path, subject, is_structured in books_to_process:
        if is_structured:
            data = parse_structured_book(path, key, subject)
        else:
            data = parse_adaptive_book(path, key, subject)
        
        if data:
            units_cnt = len(data["units"])
            lessons_cnt = sum(len(u["lessons"]) for u in data["units"])
            elems_cnt = sum(sum(len(l["elements"]) for l in u["lessons"]) for u in data["units"])
            summary.append({
                "key": key,
                "subject": subject,
                "file": os.path.basename(path),
                "units": units_cnt,
                "lessons": lessons_cnt,
                "elements": elems_cnt
            })

    print("\n========================================")
    print("SUMMARY OF ALL CONVERTED JSON BOOKS:")
    for s in summary:
        print(f"- {s['subject']} ({s['key']}.json): {s['units']} Units | {s['lessons']} Lessons | {s['elements']} Elements")

if __name__ == "__main__":
    main()
