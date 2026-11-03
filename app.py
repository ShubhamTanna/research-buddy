"""Research Buddy: search academic papers by topic and (optionally) get AI summaries.

Sources: arXiv and Crossref.
AI summaries: Google Gemini (only if GEMINI_API_KEY is set).
Keys are read from environment variables. Never hard-code them.
"""
import os
import re
import time

import feedparser
import requests
import streamlit as st

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Tried in order if the main model is busy or unavailable (comma-separated in the secret)
GEMINI_FALLBACK_MODELS = [m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash-lite").split(",") if m.strip()]
TIMEOUT = 15


def clean(text):
    """Strip XML/HTML tags (Crossref abstracts use JATS markup) and squeeze whitespace."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or "")).strip()


def fetch_arxiv_papers(query, max_results=5):
    r = requests.get("https://export.arxiv.org/api/query",
                     params={"search_query": f"all:{query}", "start": 0, "max_results": max_results},
                     timeout=TIMEOUT)
    r.raise_for_status()
    feed = feedparser.parse(r.text)
    return [{"source": "arXiv", "title": clean(e.title), "summary": clean(e.summary),
             "url": e.get("link")} for e in feed.entries]


def fetch_crossref_papers(query, max_results=5):
    r = requests.get("https://api.crossref.org/works",
                     params={"query": query, "rows": max_results}, timeout=TIMEOUT)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", [])
    return [{"source": "Crossref", "title": clean((p.get("title") or ["No title"])[0]),
             "summary": clean(p.get("abstract")) or "No abstract available.",
             "url": p.get("URL")} for p in items]


def fetch_all_sources(query, max_results=5):
    papers, errors = [], []
    for name, fetch in [("arXiv", fetch_arxiv_papers), ("Crossref", fetch_crossref_papers)]:
        try:
            papers.extend(fetch(query, max_results))
        except Exception as exc:  # one failing source should not break the others
            errors.append(f"{name} is unavailable right now ({type(exc).__name__}).")
    return papers, errors


def summarize(abstract, models):
    """Two-sentence plain-English summary of an abstract, via Gemini (google-genai SDK).

    Tries each model in order; a busy model (503/429) gets one quick retry before moving on.
    Returns (summary, model_used). Raises the last error if every model fails.
    """
    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = ("Summarise this research abstract in two plain-English sentences for a "
              "student deciding whether to read the paper. Do not add facts.\n\n" + abstract)
    last_error = None
    for model in models:
        for attempt in range(2):
            try:
                return client.models.generate_content(model=model, contents=prompt).text, model
            except Exception as exc:  # busy, retired or unknown model: try the next one
                last_error = exc
                busy = any(code in str(exc) for code in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED"))
                if busy and attempt == 0:
                    time.sleep(2)
                    continue
                break
    raise last_error


st.title("Research Buddy")
st.caption("Find academic papers on a topic, read the abstracts, and open the sources.")
query = st.text_input("Research topic", placeholder="e.g. football player detection")
n = st.slider("Results per source", 3, 10, 5)
want_ai = st.checkbox("Add AI summaries", value=bool(GEMINI_API_KEY),
                      disabled=not GEMINI_API_KEY)

if st.button("Search") and query.strip():
    with st.spinner("Searching..."):
        papers, errors = fetch_all_sources(query.strip(), n)
    for e in errors:
        st.warning(e)
    st.write(f"**{len(papers)} papers found**")
    models = [GEMINI_MODEL] + [m for m in GEMINI_FALLBACK_MODELS if m != GEMINI_MODEL]
    ai_available = True
    for p in papers:
        st.subheader(p["title"])
        st.caption(p["source"])
        if want_ai and ai_available and p["summary"] != "No abstract available.":
            try:
                text, used = summarize(p["summary"], models)
                models = [used] + [m for m in models if m != used]  # keep using what worked
                st.info(text)
            except Exception:
                ai_available = False  # don't keep retrying for every paper
                st.warning("AI summaries are unavailable right now (Google's model is busy). "
                           "The abstracts are below; try again in a few minutes.")
        with st.expander("Abstract"):
            st.write(p["summary"])
        if p.get("url"):
            st.markdown(f"[Open source]({p['url']})")
