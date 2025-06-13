from flask import Flask, render_template, request, redirect, url_for, session
import os
from werkzeug.utils import secure_filename
from finchat_core import *
from spacy import load as spacy_load
from spacy import displacy
import base64
from io import BytesIO
import pandas as pd

import matplotlib
matplotlib.use('Agg')  # <- Prevents Tkinter thread crashes
import matplotlib.pyplot as plt

from matplotlib import colormaps
from collections import defaultdict
import numpy as np
from dotenv import load_dotenv
import plotly.graph_objs as go
import plotly.io as pio


load_dotenv()
nlp = spacy_load("en_core_web_sm")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "txt"}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

USERNAME = "admin"
PASSWORD = "vinnlp2024"

default_colours = list(colormaps['tab10'].colors)
colour_cycle = iter(default_colours)

def get_next_colour():
    global colour_cycle
    try:
        rgb = next(colour_cycle)
    except StopIteration:
        colour_cycle = iter(default_colours)  # reset
        rgb = next(colour_cycle)
    return f"rgb({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)})"


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Shared state
pdf_text_cache = {}
toc_cache = []
keyword_colours = {}
tracked_keywords = []

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["logged_in"] = True
            return redirect(url_for("structure"))
        else:
            return render_template("login.html", error="Invalid credentials.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/structure", methods=["GET", "POST"])
def structure():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    result = None

    if request.method == "POST":
        file = request.files.get("pdf_file")
        question = request.form.get("question")

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            section_titles = load_section_titles("goldstandard_keywordlist.txt")
            toc_page = find_toc_page(filepath, section_titles)

            if toc_page:
                toc_sections, sorted_toc = process_toc(filepath, toc_page, section_titles)
                cached_text = load_or_cache_pdf(filepath)

                pdf_text_cache["content"] = cached_text
                toc_cache.clear()
                toc_cache.extend(sorted_toc)

                if question:
                    result = query_section_from_pdf(cached_text, 1, 10, question)
                else:
                    result = "✅ Structure extracted. No question was asked."
            else:
                result = "❌ No Table of Contents found."
        else:
            result = "❌ Invalid file or no file uploaded."

    section_list = toc_cache  # <-- always assign this outside POST block
    return render_template("structure.html", result=result, section_list=section_list)

@app.route("/finchat", methods=["GET", "POST"])
def finchat():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    answer = ""
    cached_text = pdf_text_cache.get("content")
    if request.method == "POST" and cached_text:
        start_page = int(request.form.get("start_page", 1))
        end_page = int(request.form.get("end_page", 5))
        question = request.form.get("question", "")
        if question.strip():
            answer = query_section_from_pdf(cached_text, start_page, end_page, question)

    return render_template("finchat.html", answer=answer)

@app.route("/ner", methods=["GET", "POST"])
def ner():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    selected_title = request.args.get("section")
    rendered_html = ""
    toc = toc_cache
    cached_text = pdf_text_cache.get("content")
    if selected_title and toc and cached_text:
        section_dict = {title: page for title, page in toc}
        page = section_dict.get(selected_title, 1)
        text = cached_text[page - 1] if page - 1 < len(cached_text) else ""
        text = text.replace("\n", " ")
        doc = nlp(text[:5000])
        rendered_html = displacy.render(doc, style="ent", minify=True)

    return render_template("ner.html", sections=toc or [], selected=selected_title, ner_html=rendered_html)

@app.route("/trends", methods=["GET", "POST"])
def trends():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    msg = ""
    chart = None
    table_html = None
    cached_text = pdf_text_cache.get("content")

    if request.method == "POST":
        action = request.form.get("action")
        keyword = request.form.get("keyword", "").strip().lower()

        if action == "add" and keyword and keyword not in tracked_keywords:
            tracked_keywords.append(keyword)
            keyword_colours[keyword] = get_next_colour()
            msg = f"✅ Added keyword: {keyword}"

        elif action == "remove":
            if keyword in tracked_keywords:
                tracked_keywords.remove(keyword)
                keyword_colours.pop(keyword, None)
                msg = f"❌ Removed keyword: {keyword}"
            else:
                msg = f"⚠️ Keyword '{keyword}' not found."

        elif action == "clear":
            tracked_keywords.clear()
            keyword_colours.clear()
            return redirect(url_for("trends"))  # ✅ refresh after clearing

        elif action == "upload" and "txt_file" in request.files:
            f = request.files["txt_file"]
            if f and allowed_file(f.filename):
                content = f.read().decode("utf-8", errors="ignore")
                new_words = set(content.split())
                added = 0
                for w in new_words:
                    word = w.strip().lower()
                    if word and word not in tracked_keywords:
                        tracked_keywords.append(word)
                        keyword_colours[word] = get_next_colour()  # ✅ fix here
                        added += 1
                msg = f"✅ Added {added} words."

        elif action == "show_table" and cached_text:
            joined_text = "\n".join(cached_text).lower()
            chunk_size = len(joined_text) // 100
            keyword_freq_table = defaultdict(int)
            for word in tracked_keywords:
                for i in range(100):
                    chunk = joined_text[i * chunk_size:(i + 1) * chunk_size]
                    keyword_freq_table[word] += chunk.count(word)
            df = pd.DataFrame(keyword_freq_table.items(), columns=["Keyword", "Total Frequency"])
            df = df.sort_values(by="Total Frequency", ascending=False)
            table_html = df.to_html(classes="table table-striped", index=False, border=0)

    # ✅ Plotly interactive chart generation
    if cached_text and tracked_keywords:
        joined_text = "\n".join(cached_text).lower()
        chunk_size = len(joined_text) // 100
        x = list(range(1, 101))
        traces = []

        keyword_freq_table = defaultdict(int)

        for word in tracked_keywords:
            y = [joined_text[i * chunk_size:(i + 1) * chunk_size].count(word) for i in range(100)]
            for val in y:
                keyword_freq_table[word] += val

            # Convert (r, g, b) to CSS string
            rgb = keyword_colours.get(word, (0, 0, 0))
            if isinstance(rgb, str):
                colour = rgb  # it's already a string like 'rgb(255,0,0)' or 'blue'
            else:
                colour = f"rgb({int(rgb[0]*255)}, {int(rgb[1]*255)}, {int(rgb[2]*255)})"


            trace = go.Scatter(
                x=x,
                y=y,
                mode='lines+markers',
                name=word,
                line=dict(color=colour),
                hovertemplate=f"<b>{word}</b><br>Chunk: %{{x}}<br>Freq: %{{y}}<extra></extra>"
            )
            traces.append(trace)

        layout = go.Layout(
            title="Keyword Frequency Trends",
            xaxis=dict(title="Report Progress (1–100 chunks)"),
            yaxis=dict(title="Frequency"),
            hovermode='closest'
        )

        fig = go.Figure(data=traces, layout=layout)
        chart = pio.to_html(fig, full_html=False)

        # ✅ Always generate the table
        df = pd.DataFrame(keyword_freq_table.items(), columns=["Keyword", "Total Frequency"])
        df = df.sort_values(by="Total Frequency", ascending=False)
        table_html = df.to_html(classes="table table-striped", index=False, border=0)
    

    return render_template("trends.html", keywords=tracked_keywords, chart=chart, msg=msg, table_html=table_html)

if __name__ == "__main__":
    app.run(debug=True)