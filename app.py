"""Research Buddy: search academic papers by topic and (optionally) get AI summaries.

Sources: arXiv (always on), Crossref (always on), IEEE Xplore (only if IEEE_API_KEY is set).
AI summaries: Google Gemini (only if GEMINI_API_KEY is set).
Keys are read from environment variables. Never hard-code them.
"""
import os
import re

import feedparser
import requests
import streamlit as st

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
IEEE_API_KEY = os.getenv("IEEE_API_KEY")
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


def fetch_ieee_papers(query, max_results=5):
    if not IEEE_API_KEY:
        return []
    r = requests.get("https://ieeexploreapi.ieee.org/api/v1/search/articles",
                     params={"querytext": query, "apikey": IEEE_API_KEY,
                             "max_records": max_results}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{"source": "IEEE Xplore", "title": clean(p.get("title", "No title")),
             "summary": clean(p.get("abstract")) or "No abstract available.",
             "url": p.get("html_url") or p.get("pdf_url")} for p in r.json().get("articles", [])]


def fetch_all_sources(query, max_results=5):
    papers, errors = [], []
    for name, fetch in [("arXiv", fetch_arxiv_papers), ("Crossref", fetch_crossref_papers),
                        ("IEEE Xplore", fetch_ieee_papers)]:
        try:
            papers.extend(fetch(query, max_results))
        except Exception as exc:  # one failing source should not break the others
            errors.append(f"{name} is unavailable right now ({type(exc).__name__}).")
    return papers, errors


def summarize(abstract):
    """Two-sentence plain-English summary of an abstract, via Gemini (google-genai SDK)."""
    from google import genai
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = ("Summarise this research abstract in two plain-English sentences for a "
              "student deciding whether to read the paper. Do not add facts.\n\n" + abstract)
    return client.models.generate_content(model=GEMINI_MODEL, contents=prompt).text


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
    for p in papers:
        st.subheader(p["title"])
        st.caption(p["source"])
        if want_ai and p["summary"] != "No abstract available.":
            try:
                st.info(summarize(p["summary"]))
            except Exception as exc:
                st.caption(f"AI summary unavailable: {exc}")
        with st.expander("Abstract"):
            st.write(p["summary"])
        if p.get("url"):
            st.markdown(f"[Open source]({p['url']})")
