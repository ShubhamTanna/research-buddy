# Research Buddy

**A personal tool that searches arXiv and Crossref at once and adds optional two-sentence AI summaries, so you can decide in seconds whether a paper is worth reading.**

## The problem

Literature reviews for my college projects meant searching three databases separately and skimming dozens of abstracts. I built Research Buddy in April 2025 to do the searching in one place, and rebuilt it in October 2026.

## Approach

- **One query, two sources:** arXiv and Crossref, merged into one list.
- **Fails gracefully:** each source has its own timeout and error handling, so one outage still leaves results from the others, with a clear warning.
- **Clean abstracts:** strips the JATS/XML markup Crossref returns.
- **Optional AI summaries:** two plain-English sentences per abstract from Google Gemini (`google-genai` SDK). The prompt tells the model not to add facts.

## Run it

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...      # optional: enables AI summaries
streamlit run app.py
```

On Streamlit Community Cloud, put the keys in the app's **Secrets** as `GEMINI_API_KEY = "..."`; never commit them.

## Version history

- **April 2025:** arXiv + IEEE + Crossref search in Streamlit. Gemini summarisation was written but never wired to the interface; Google Scholar was tried and dropped.
- **October 2026 rebuild:** API keys moved out of the code into environment variables; IEEE Xplore dropped (it needs an approved developer key); timeouts and per-source error handling; HTTPS for arXiv; Crossref queries encoded and abstracts cleaned; AI summaries moved to the current SDK, connected and made optional; unused Scholar dependency removed.

## Limitations

- A discovery tool, not a systematic-review platform: no de-duplication across sources, citation export or full-text analysis.
- AI summaries come from the abstract only. Check them against the paper.
- Crossref often has no abstract.

---
**Shubham Tanna** · Python, Streamlit, REST APIs, Google Gemini
<!-- SITE_LINK:work/research-buddy -->
