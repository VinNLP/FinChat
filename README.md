# 📊 FinXtract: LLM-Powered Annual Report Insight Tool

**FinXtract** is an LLM-powered tool that transforms annual reports into structured, searchable, and insightful data — with no manual rule-writing.

## 🚀 What It Does

Upload a full annual report (PDF or text), and FinXtract will:

- 🗂 **Detect Document Structure**  
  Identify key sections (e.g. Chairman’s Statement, Risk Disclosure) and map them to page numbers

- 📄 **Extract Section Text**  
  Retrieve and display full text for each detected section

- 🧾 **Named Entity Recognition (NER)**  
  Automatically annotate entities like names, roles, organisations, and locations

- ❓ **Question Answering**  
  Ask natural-language questions about the company or report  
  _e.g. “Who is the chairman?”, “What risks are mentioned?”_

- 📈 **Keyword Tracking & Chart Generation**  
  Analyse keyword trends and visualise them across the report

## 🧠 Powered By

- 🔗 Large Language Models (LLMs)  
- 💬 Prompt Engineering  
- 🐍 Python + Streamlit (or Flask)  
- 📄 PDF/Text parsing (e.g. PyMuPDF)

## 💼 Use Cases

- Financial and ESG analysts
- Regulatory and audit teams
- NLP researchers and students
- Anyone working with complex corporate disclosures

## 🏁 Getting Started

```bash
git clone https://github.com/yourusername/finxtract.git
cd finxtract
pip install -r requirements.txt
python app.py
