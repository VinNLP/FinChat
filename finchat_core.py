import os
import re
import pdfplumber
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def load_section_titles(filepath):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return [line.strip().lower() for line in f if line.strip()]

def clean_line(line):
    return re.sub(r'[^a-zA-Z0-9 ]', '', line).strip().lower()

def find_toc_page(pdf_path, section_titles, threshold=5):
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                continue
            lines = [clean_line(line) for line in text.split('\n')]
            match_count = sum(1 for line in lines if any(st in line for st in section_titles))
            if match_count >= threshold:
                return i + 1
    return None

def extract_all_sections_from_line(pdf_path, toc_page_number, gold_keywords):
    extracted_sections = []
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[toc_page_number - 1]
        text = page.extract_text()
        if not text:
            return extracted_sections
        lines = text.split('\n')
        for line in lines:
            match = re.match(r"^(.*?)(\.{2,}|\s{2,})(\d{1,3})$", line.strip())
            if not match:
                continue
            section_candidate = match.group(1).strip()
            reported_page_str = match.group(3).strip()
            cleaned_section = clean_line(section_candidate)
            if any(kw in cleaned_section for kw in gold_keywords):
                try:
                    extracted_sections.append({
                        "section": section_candidate,
                        "reported_page": int(reported_page_str),
                        "actual_pdf_page": None
                    })
                except ValueError:
                    continue
    return extracted_sections

def parse_and_sort_toc(gpt_result):
    lines = gpt_result.strip().split('\n')
    sections = []
    for line in lines:
        if '|' in line:
            try:
                title, page = line.split('|')
                title = title.strip().lstrip('- ').strip()
                page = int(page.strip().lstrip('0') or "0")
                sections.append((title, page))
            except ValueError:
                continue
    return sorted(sections, key=lambda x: x[1])

def send_toc_to_gpt(toc_text):
    prompt = f"""This is the table of contents of a financial annual report. Extract a clean, structured list of section titles with their corresponding page numbers. Avoid repeating company headers. Provide a list in this format:\n\nSection Title | Logical Page Number\n\nHere is the content:\n\n{toc_text}"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def load_or_cache_pdf(pdf_path):
    full_text_by_page = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            full_text_by_page.append(text if text else "")
    return full_text_by_page

def query_section_from_pdf(cached_text, start_page, end_page, user_question):
    section_text = "\n".join(cached_text[start_page - 1:end_page])
    prompt = f"""You are reading part of a financial annual report. Answer the following question based only on the content provided.\n\nQuestion: {user_question}\n\nContent:\n{section_text}"""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    return response.choices[0].message.content

def process_toc(pdf_path, toc_page, section_titles):
    toc_sections = extract_all_sections_from_line(pdf_path, toc_page, section_titles)
    with pdfplumber.open(pdf_path) as pdf:
        raw_toc_text = pdf.pages[toc_page - 1].extract_text()
    gpt_result = send_toc_to_gpt(raw_toc_text)
    sorted_toc = parse_and_sort_toc(gpt_result)
    return toc_sections, sorted_toc