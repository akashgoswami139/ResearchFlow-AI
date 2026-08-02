from __future__ import annotations
 
import io
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
 
import streamlit as st
import streamlit.components.v1 as components
 
try:
    from streamlit_option_menu import option_menu
    HAS_OPTION_MENU = True
except Exception:
    HAS_OPTION_MENU = False
 
# ============================================================================
# BACKEND IMPORT (isolated so the app doesn't crash if agent.py / keys are
# missing — pipeline.py itself is never modified or reimplemented here)
# ============================================================================
PIPELINE_IMPORT_ERROR: Optional[str] = None
try:
    from pipeline import run_research_pipeline  # noqa: F401
    PIPELINE_AVAILABLE = True
except Exception as exc:  # pragma: no cover - environment dependent
    PIPELINE_AVAILABLE = False
    PIPELINE_IMPORT_ERROR = str(exc)
 
    def run_research_pipeline(topic: str) -> dict:  # type: ignore
        raise RuntimeError(
            "pipeline.py could not be loaded: "
            f"{PIPELINE_IMPORT_ERROR}. Make sure pipeline.py and agent.py "
            "(with build_search_agent, build_reader_agent, writer_chain, "
            "critic_chain) are present in the app directory, and that any "
            "required API keys are set."
        )
 
APP_NAME = "ResearchFlow AI"
TAGLINE = "Enterprise Multi-Agent AI Research Assistant"
EXAMPLE_TOPICS = ["Artificial Intelligence", "Tesla", "Climate Change", "Quantum Computing", "AI Hiring Process"]
PAGES = ["Home", "Research", "Generated Reports", "Working Process", "Settings", "About"]
PAGE_ICONS = ["house", "search", "file-earmark-text", "diagram-3", "gear", "info-circle"]
 
URL_PATTERN = re.compile(r"https?://[^\s\)\]\"'>,]+")
 
 
# ============================================================================
# DATA HELPERS (only normalize/measure what pipeline.py already returns)
# ============================================================================
def to_text(value: Any) -> str:
    """Normalize whatever pipeline.py returns for a field into plain text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(value, dict):
        for key in ("content", "text", "output", "report"):
            if key in value and isinstance(value[key], str):
                return value[key]
    return str(value)
 
 
def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    seen: List[str] = []
    for match in URL_PATTERN.findall(text):
        cleaned = match.rstrip(".,;:")
        if cleaned not in seen:
            seen.append(cleaned)
    return seen
 
 
def count_words(text: str) -> int:
    return len(text.split()) if text else 0
 
 
def estimate_reading_time(word_count: int, words_per_minute: int = 200) -> int:
    return max(1, round(word_count / words_per_minute)) if word_count > 0 else 0
 
 
def try_extract_score(feedback_text: str) -> Optional[str]:
    """Best-effort score extraction; returns None rather than a fake number."""
    if not feedback_text:
        return None
    patterns = [
        r"(?:overall\s+score|score|rating)\s*[:\-]?\s*(\d{1,3}\s*/\s*\d{1,3})",
        r"(?:overall\s+score|score|rating)\s*[:\-]?\s*(\d{1,3}\s*(?:%|percent))",
        r"(?:overall\s+score|score|rating)\s*[:\-]?\s*(\d(?:\.\d)?\s*/\s*10)",
    ]
    for pattern in patterns:
        match = re.search(pattern, feedback_text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None
 
 
@dataclass
class ResearchRun:
    id: str
    topic: str
    created_at: str
    search_results: str
    scraped_content: str
    report: str
    feedback: str
    execution_seconds: float
    error: Optional[str] = None
 
    @property
    def word_count(self) -> int:
        return count_words(self.report)
 
    @property
    def reading_minutes(self) -> int:
        return estimate_reading_time(self.word_count)
 
    @property
    def sources(self) -> List[str]:
        return extract_urls(self.search_results)
 
    @property
    def score(self) -> Optional[str]:
        return try_extract_score(self.feedback)
 
 
def run_pipeline_safely(topic: str) -> ResearchRun:
    """Call the real backend, timing it, never fabricating data on failure."""
    start = time.perf_counter()
    run_id = str(uuid.uuid4())[:8]
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        state: Dict[str, Any] = run_research_pipeline(topic)
        elapsed = time.perf_counter() - start
        return ResearchRun(
            id=run_id, topic=topic, created_at=created_at,
            search_results=to_text(state.get("search_results", "")),
            scraped_content=to_text(state.get("scraped_content", "")),
            report=to_text(state.get("report", "")),
            feedback=to_text(state.get("feedback", "")),
            execution_seconds=elapsed, error=None,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - start
        return ResearchRun(
            id=run_id, topic=topic, created_at=created_at,
            search_results="", scraped_content="", report="", feedback="",
            execution_seconds=elapsed, error=str(exc),
        )
 
 
def build_markdown_document(run: ResearchRun) -> str:
    urls = run.sources
    sources_block = "\n".join(f"- {u}" for u in urls) if urls else "_No source URLs detected in search output._"
    return f"""# Research Report: {run.topic}
 
*Generated by ResearchFlow AI on {run.created_at}*
 
---
 
## Report
 
{run.report}
 
---
 
## Critic Review
 
{run.feedback}
 
---
 
## Sources Referenced
 
{sources_block}
 
---
 
*Word count: {run.word_count} | Estimated reading time: {run.reading_minutes} min | Generation time: {run.execution_seconds:.1f}s*
"""
 
 
def build_plain_text_document(run: ResearchRun) -> str:
    urls = run.sources
    sources_block = "\n".join(f"- {u}" for u in urls) if urls else "No source URLs detected."
    return (
        f"RESEARCH REPORT: {run.topic}\nGenerated: {run.created_at}\n{'=' * 60}\n\n"
        f"REPORT\n{'-' * 60}\n{run.report}\n\n"
        f"CRITIC REVIEW\n{'-' * 60}\n{run.feedback}\n\n"
        f"SOURCES\n{'-' * 60}\n{sources_block}\n"
    )
 
 
def build_pdf_bytes(run: ResearchRun) -> Optional[bytes]:
    """Render to PDF via fpdf2 if installed; returns None otherwise."""
    try:
        from fpdf import FPDF
    except Exception:
        return None
 
    def sanitize(text: str) -> str:
        return text.encode("latin-1", "replace").decode("latin-1") if text else ""

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_left_margin(10)
    pdf.set_right_margin(10)

    page_width = pdf.w - pdf.l_margin - pdf.r_margin

    # ---------- Define section() HERE ----------
    def section(title: str, body: str):
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "B", 13)
        pdf.multi_cell(page_width, 8, sanitize(title))

        pdf.set_x(pdf.l_margin)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(page_width, 5.5, sanitize(body or "Not available."))

        pdf.ln(3)

    # ---------- PDF Header ----------
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(page_width, 10, sanitize(f"Research Report: {run.topic}"))

    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(page_width, 6, sanitize(f"Generated: {run.created_at}"))

    pdf.ln(4)

    # ---------- Use section() ----------
    section("Report", run.report)
    section("Critic Review", run.feedback)

    urls = run.sources
    section("Sources Referenced", "\n".join(urls) if urls else "No source URLs detected.")

    buffer = io.BytesIO()
    pdf.output(buffer)
    return buffer.getvalue()
 
# ============================================================================
# THEME / CSS  ("research ledger" look: ink + brass/amber + teal accents)
# ============================================================================
FONT_SCALES = {"Small": "14px", "Medium": "16px", "Large": "18px"}
 
_DARK_TOKENS = {
    "bg": "#12161F", "surface": "#1B2130", "paper": "#232A3D", "paper_hover": "#28304A",
    "border": "rgba(237, 239, 244, 0.08)", "text": "#EDEFF4", "muted": "#8A93A6",
    "accent": "#E3A857", "accent_ink": "#2A2210", "teal": "#4FB0A5", "error": "#E2685B",
}
_LIGHT_TOKENS = {
    "bg": "#F2F3F6", "surface": "#FFFFFF", "paper": "#EDEFF5", "paper_hover": "#E3E7F0",
    "border": "rgba(23, 26, 33, 0.08)", "text": "#171A21", "muted": "#5B6472",
    "accent": "#B9791F", "accent_ink": "#FFF6E6", "teal": "#0F7A6E", "error": "#C6483B",
}
 
 
def get_custom_css(theme: str = "Dark", font_size: str = "Medium", animations: bool = True) -> str:
    t = _DARK_TOKENS if theme == "Dark" else _LIGHT_TOKENS
    base_font = FONT_SCALES.get(font_size, "16px")
    transition = "all 0.18s ease" if animations else "none"
    fade_anim = (
        "@keyframes rfFadeIn { from { opacity: 0; transform: translateY(6px);} to {opacity: 1; transform: translateY(0);} }"
        if animations else ""
    )
    fade_rule = "animation: rfFadeIn 0.35s ease both;" if animations else ""
 
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
 
:root {{
    --rf-bg: {t['bg']}; --rf-surface: {t['surface']}; --rf-paper: {t['paper']};
    --rf-paper-hover: {t['paper_hover']}; --rf-border: {t['border']}; --rf-text: {t['text']};
    --rf-muted: {t['muted']}; --rf-accent: {t['accent']}; --rf-accent-ink: {t['accent_ink']};
    --rf-teal: {t['teal']}; --rf-error: {t['error']}; --rf-font-base: {base_font};
}}
{fade_anim}
html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main {{
    background-color: var(--rf-bg) !important; color: var(--rf-text) !important;
    font-family: 'Inter', sans-serif !important; font-size: var(--rf-font-base);
}}
section[data-testid="stSidebar"] {{ background-color: var(--rf-surface) !important; border-right: 1px solid var(--rf-border); }}
section[data-testid="stSidebar"] * {{ color: var(--rf-text) !important; }}
h1, h2, h3, .rf-display {{ font-family: 'Fraunces', serif !important; letter-spacing: -0.01em; }}
code, pre, .rf-mono {{ font-family: 'JetBrains Mono', monospace !important; }}
 
.rf-hero {{
    padding: 3rem 2.5rem; border-radius: 20px;
    background: linear-gradient(135deg, var(--rf-surface) 0%, var(--rf-paper) 100%);
    border: 1px solid var(--rf-border); margin-bottom: 2rem; {fade_rule}
}}
.rf-hero-title {{ font-family: 'Fraunces', serif; font-size: 2.6rem; font-weight: 700; margin: 0 0 0.35rem 0; }}
.rf-hero-tagline {{
    font-family: 'JetBrains Mono', monospace; color: var(--rf-accent); font-size: 0.95rem;
    letter-spacing: 0.06em; text-transform: uppercase; margin-bottom: 1rem;
}}
.rf-hero-desc {{ color: var(--rf-muted); font-size: 1.05rem; max-width: 680px; line-height: 1.6; }}
 
.rf-card {{
    background-color: var(--rf-paper); border: 1px solid var(--rf-border); border-radius: 16px;
    padding: 1.4rem 1.5rem; margin-bottom: 1rem; transition: {transition}; {fade_rule}
}}
.rf-card:hover {{ background-color: var(--rf-paper-hover); transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.18); }}
.rf-feature-icon {{ font-size: 1.8rem; margin-bottom: 0.5rem; }}
.rf-feature-title {{ font-weight: 600; font-size: 1.05rem; margin-bottom: 0.3rem; }}
.rf-feature-desc {{ color: var(--rf-muted); font-size: 0.92rem; line-height: 1.5; }}
 
.rf-ledger {{ position: relative; padding-left: 2.2rem; margin: 1.5rem 0; }}
.rf-ledger::before {{
    content: ""; position: absolute; left: 0.65rem; top: 0.4rem; bottom: 0.4rem; width: 2px;
    background: linear-gradient(var(--rf-accent), var(--rf-teal)); opacity: 0.5;
}}
.rf-ledger-step {{ position: relative; margin-bottom: 1.6rem; }}
.rf-ledger-step::before {{
    content: attr(data-index); position: absolute; left: -2.2rem; top: 0; width: 1.5rem; height: 1.5rem;
    border-radius: 50%; background: var(--rf-paper); border: 2px solid var(--rf-accent); color: var(--rf-accent);
    font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; display: flex; align-items: center; justify-content: center;
}}
 
.rf-badge {{ display: inline-block; padding: 0.2rem 0.7rem; border-radius: 999px; font-size: 0.78rem; font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
.rf-badge-success {{ background: rgba(79,176,165,0.15); color: var(--rf-teal); }}
.rf-badge-warning {{ background: rgba(227,168,87,0.15); color: var(--rf-accent); }}
.rf-badge-error {{ background: rgba(226,104,91,0.15); color: var(--rf-error); }}
 
.rf-metric-row {{ display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 0.75rem 0; }}
.rf-metric-pill {{
    background: var(--rf-surface); border: 1px solid var(--rf-border); border-radius: 10px;
    padding: 0.5rem 0.9rem; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--rf-text);
}}
.rf-metric-pill b {{ color: var(--rf-accent); }}
 
div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {{
    border-radius: 10px !important; border: 1px solid var(--rf-border) !important;
    background: var(--rf-paper) !important; color: var(--rf-text) !important; font-weight: 600 !important; transition: {transition};
}}
div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover {{
    border-color: var(--rf-accent) !important; color: var(--rf-accent) !important;
}}
div[data-testid="stButton"] button[kind="primary"] {{ background: var(--rf-accent) !important; color: var(--rf-accent-ink) !important; border: none !important; }}
div[data-testid="stButton"] button[kind="primary"]:hover {{ filter: brightness(1.08); color: var(--rf-accent-ink) !important; }}
 
.rf-divider {{ height: 1px; background: var(--rf-border); margin: 1.75rem 0; border: none; }}
.rf-muted {{ color: var(--rf-muted); }}
.rf-section-eyebrow {{ font-family: 'JetBrains Mono', monospace; text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem; color: var(--rf-teal); margin-bottom: 0.4rem; }}
.rf-social-link {{
    display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border-radius: 10px;
    background: var(--rf-paper); border: 1px solid var(--rf-border); color: var(--rf-text) !important;
    text-decoration: none !important; margin: 0.3rem 0.4rem 0.3rem 0; font-weight: 500; transition: {transition};
}}
.rf-social-link:hover {{ border-color: var(--rf-accent); color: var(--rf-accent) !important; }}
</style>
"""
 
 
# ============================================================================
# SESSION STATE
# ============================================================================
def init_session_state() -> None:
    defaults = {
        "reports": [], "current_run": None, "theme": "Dark",
        "font_size": "Medium", "animations": True, "topic_input": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
 
 
def inject_css() -> None:
    st.markdown(
        get_custom_css(st.session_state["theme"], st.session_state["font_size"], st.session_state["animations"]),
        unsafe_allow_html=True,
    )
 
 
# ============================================================================
# SMALL REUSABLE UI HELPERS
# ============================================================================
def copy_button(text: str, label: str, key: str) -> None:
    safe_text = json.dumps(text or "")
    html = f"""
    <div style="margin-top:0.25rem;">
      <button id="{key}"
        style="padding:0.45rem 0.9rem;border-radius:10px;border:1px solid rgba(128,128,128,0.3);
        background:transparent;color:inherit;cursor:pointer;font-family:Inter,sans-serif;font-size:0.85rem;">
        📋 {label}
      </button>
      <span id="{key}-msg" style="margin-left:0.5rem;font-size:0.8rem;opacity:0.7;"></span>
    </div>
    <script>
      const btn_{key} = document.getElementById("{key}");
      btn_{key}.addEventListener("click", function() {{
        navigator.clipboard.writeText({safe_text}).then(function() {{
          document.getElementById("{key}-msg").innerText = "Copied!";
          setTimeout(function() {{ document.getElementById("{key}-msg").innerText = ""; }}, 1500);
        }});
      }});
    </script>
    """
    components.html(html, height=50)
 
 
def badge(text: str, kind: str = "success") -> str:
    return f'<span class="rf-badge rf-badge-{kind}">{text}</span>'
 
 
def metric_pill(label: str, value: str) -> str:
    return f'<div class="rf-metric-pill">{label}: <b>{value}</b></div>'
 
 
def render_feature_card(icon: str, title: str, desc: str) -> None:
    st.markdown(
        f'<div class="rf-card"><div class="rf-feature-icon">{icon}</div>'
        f'<div class="rf-feature-title">{title}</div><div class="rf-feature-desc">{desc}</div></div>',
        unsafe_allow_html=True,
    )
 
 
# ============================================================================
# PAGES
# ============================================================================
def page_home() -> None:
    st.markdown(
        f"""
        <div class="rf-hero">
            <div class="rf-hero-tagline">{TAGLINE}</div>
            <div class="rf-hero-title">🧭 {APP_NAME}</div>
            <div class="rf-hero-desc">
                ResearchFlow AI is an Enterprise Multi-Agent Research Assistant capable of
                searching the web, reading trusted sources, generating professional research
                reports, and reviewing them using autonomous AI agents.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
    if not PIPELINE_AVAILABLE:
        st.warning(
            "Backend not detected yet. Add `pipeline.py` and `agent.py` "
            "(with `build_search_agent`, `build_reader_agent`, `writer_chain`, "
            f"`critic_chain`) to this folder to activate research. Details: {PIPELINE_IMPORT_ERROR}"
        )
 
    st.markdown('<div class="rf-section-eyebrow">Capabilities</div>', unsafe_allow_html=True)
    cols = st.columns(3)
    features = [
        ("🔍", "Intelligent Search", "Finds recent, reliable sources across the web for any topic."),
        ("📖", "Content Reader", "Scrapes and cleans the most relevant source into structured text."),
        ("✍", "AI Report Writer", "Synthesizes research into a structured, well-referenced report."),
        ("🧠", "Report Critic", "Independently reviews the report and surfaces improvement notes."),
        ("🌐", "Web Intelligence", "Grounded in live web content rather than static training data."),
        ("⚡", "Fast Processing", "A single pipeline call orchestrates all four agents end to end."),
    ]
    for i, (icon, title, desc) in enumerate(features):
        with cols[i % 3]:
            render_feature_card(icon, title, desc)
 
    st.markdown('<hr class="rf-divider">', unsafe_allow_html=True)
    left, right = st.columns([3, 1])
    with left:
        st.markdown("Ready to start? Head to **🔍 Research** in the sidebar to run your first report.")
    with right:
        if st.button("Go to Research →", type="primary", use_container_width=True):
            st.session_state["_nav_override"] = "Research"
            st.rerun()
 
 
def _agent_status_badge(run: ResearchRun, has_content: bool) -> str:
    if run.error:
        return badge("Failed", "error")
    return badge("Completed", "success") if has_content else badge("No data", "warning")
 
 
def render_run_results(run: ResearchRun) -> None:
    if run.error:
        st.error(f"The pipeline raised an error: {run.error}")
        return
 
    st.markdown('<div class="rf-metric-row">', unsafe_allow_html=True)
    st.markdown(
        "".join([
            metric_pill("Execution time", f"{run.execution_seconds:.1f}s"),
            metric_pill("Sources found", str(len(run.sources))),
            metric_pill("Report words", str(run.word_count)),
            metric_pill("Reading time", f"{run.reading_minutes} min"),
            metric_pill("Critic score", run.score or "n/a"),
        ]),
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
 
    with st.expander("🔍 Search Agent", expanded=True):
        st.markdown(_agent_status_badge(run, bool(run.search_results)), unsafe_allow_html=True)
        st.markdown(f"**Sources found:** {len(run.sources)}")
        if run.sources:
            st.markdown("**URLs**")
            for url in run.sources:
                st.markdown(f"- [{url}]({url})")
        st.markdown("**Search results**")
        st.markdown(run.search_results or "_No content returned._")
 
    with st.expander("📖 Reader Agent", expanded=False):
        st.markdown(_agent_status_badge(run, bool(run.scraped_content)), unsafe_allow_html=True)
        st.markdown(f"**Extracted word count:** {len(run.scraped_content.split())}")
        st.markdown("**Extracted information**")
        st.markdown(run.scraped_content or "_No content returned._")
 
    with st.expander("✍ Writer Agent", expanded=True):
        st.markdown(_agent_status_badge(run, bool(run.report)), unsafe_allow_html=True)
        st.markdown(f"**Word count:** {run.word_count}  |  **Estimated reading time:** {run.reading_minutes} min")
        st.markdown("**Generated report (Markdown preview)**")
        st.markdown(run.report or "_No content returned._")
 
        md_doc = build_markdown_document(run)
        txt_doc = build_plain_text_document(run)
        dl_cols = st.columns(3)
        with dl_cols[0]:
            st.download_button("⬇ Download .md", md_doc, file_name=f"{run.topic.replace(' ', '_')}_report.md",
                                mime="text/markdown", use_container_width=True, key=f"md_{run.id}")
        with dl_cols[1]:
            st.download_button("⬇ Download .txt", txt_doc, file_name=f"{run.topic.replace(' ', '_')}_report.txt",
                                mime="text/plain", use_container_width=True, key=f"txt_{run.id}")
        with dl_cols[2]:
            pdf_bytes = build_pdf_bytes(run)
            if pdf_bytes:
                st.download_button("⬇ Download .pdf", pdf_bytes, file_name=f"{run.topic.replace(' ', '_')}_report.pdf",
                                    mime="application/pdf", use_container_width=True, key=f"pdf_{run.id}")
            else:
                st.caption("Install `fpdf2` to enable PDF export.")
        copy_button(run.report, "Copy report", key=f"copy_{run.id}")
 
    with st.expander("🧠 Critic Agent", expanded=False):
        st.markdown(_agent_status_badge(run, bool(run.feedback)), unsafe_allow_html=True)
        if run.score:
            st.markdown(badge(f"Overall score: {run.score}", "warning"), unsafe_allow_html=True)
        st.markdown("**Review**")
        st.markdown(run.feedback or "_No content returned._")
 
 
def page_research() -> None:
    st.markdown("## 🔍 Research")
    st.markdown('<p class="rf-muted">Enter a topic and let the four agents do the work.</p>', unsafe_allow_html=True)
 
    st.markdown("**Try an example:**")
    ex_cols = st.columns(len(EXAMPLE_TOPICS))
    for i, topic in enumerate(EXAMPLE_TOPICS):
        with ex_cols[i]:
            if st.button(topic, key=f"example_{i}", use_container_width=True):
                st.session_state["topic_input"] = topic
 
    topic = st.text_input(
        "Enter your research topic", value=st.session_state["topic_input"],
        placeholder="e.g. Artificial Intelligence, Tesla, Climate Change...", key="topic_input",
    )
 
    start = st.button("🚀 Start Research", type="primary", use_container_width=True, disabled=not PIPELINE_AVAILABLE)
 
    if not PIPELINE_AVAILABLE:
        st.warning(
            "Backend not detected. Add `pipeline.py` and `agent.py` to this app's folder "
            f"to enable research. ({PIPELINE_IMPORT_ERROR})"
        )
 
    if start:
        if not topic.strip():
            st.error("Please enter a research topic before starting.")
        else:
            progress = st.progress(0, text="🔍 Search Agent is finding sources...")
            with st.spinner(f"Running the ResearchFlow AI pipeline for '{topic}'..."):
                progress.progress(25, text="📖 Reader Agent is scraping content...")
                run = run_pipeline_safely(topic)
                progress.progress(75, text="✍ Writer Agent drafting, 🧠 Critic Agent reviewing...")
                progress.progress(100, text="Done.")
            progress.empty()
 
            st.session_state["current_run"] = run
            st.session_state["reports"].insert(0, run)
 
            if run.error:
                st.error(f"Research failed: {run.error}")
            else:
                st.success(f"Research complete in {run.execution_seconds:.1f}s.")
 
    st.markdown('<hr class="rf-divider">', unsafe_allow_html=True)
 
    current: Optional[ResearchRun] = st.session_state.get("current_run")
    if current:
        st.markdown(f"### Results for: *{current.topic}*")
        render_run_results(current)
    else:
        st.info("No research run yet. Enter a topic above and click **Start Research**.")
 
 
def page_reports() -> None:
    st.markdown("## 📄 Generated Reports")
    reports: List[ResearchRun] = st.session_state["reports"]
 
    if not reports:
        st.info("No reports yet. Run a research query on the **Research** page first.")
        return
 
    search_q = st.text_input("🔎 Search reports by topic", "")
    filtered = [r for r in reports if search_q.lower() in r.topic.lower()] if search_q else reports
    st.caption(f"{len(filtered)} of {len(reports)} report(s) shown.")
 
    for run in filtered:
        status = badge("Failed", "error") if run.error else badge("Completed", "success")
        with st.expander(f"{run.topic}  —  {run.created_at}"):
            st.markdown(status, unsafe_allow_html=True)
            if run.error:
                st.error(run.error)
            else:
                st.markdown(
                    "".join([
                        metric_pill("Words", str(run.word_count)),
                        metric_pill("Reading time", f"{run.reading_minutes} min"),
                        metric_pill("Sources", str(len(run.sources))),
                        metric_pill("Duration", f"{run.execution_seconds:.1f}s"),
                    ]),
                    unsafe_allow_html=True,
                )
                st.markdown(run.report[:1200] + ("..." if len(run.report) > 1200 else ""))
 
                btn_cols = st.columns(4)
                with btn_cols[0]:
                    if st.button("Open in Research", key=f"open_{run.id}", use_container_width=True):
                        st.session_state["current_run"] = run
                        st.session_state["_nav_override"] = "Research"
                        st.rerun()
                with btn_cols[1]:
                    st.download_button("Download .md", build_markdown_document(run),
                                        file_name=f"{run.topic.replace(' ', '_')}.md", mime="text/markdown",
                                        use_container_width=True, key=f"rep_md_{run.id}")
                with btn_cols[2]:
                    copy_button(run.report, "Copy", key=f"rep_copy_{run.id}")
                with btn_cols[3]:
                    if st.button("🗑 Delete", key=f"del_{run.id}", use_container_width=True):
                        st.session_state["reports"] = [r for r in reports if r.id != run.id]
                        if st.session_state["current_run"] and st.session_state["current_run"].id == run.id:
                            st.session_state["current_run"] = None
                        st.rerun()
 
 
def page_working_process() -> None:
    st.markdown("## 📊 Working Process")
    st.markdown('<p class="rf-muted">How ResearchFlow AI turns a topic into a reviewed report.</p>', unsafe_allow_html=True)
 
    st.code(
        "                User\n                  │\n                  ▼\n"
        "        🔍 Search Agent\n                  │\n                  ▼\n"
        "        📖 Reader Agent\n                  │\n                  ▼\n"
        "        ✍ Writer Agent\n                  │\n                  ▼\n"
        "        🧠 Critic Agent\n                  │\n                  ▼\n"
        "            Final Report",
        language=None,
    )
 
    steps = [
        ("🔍", "Search Agent", ["Searches trusted sources across the internet.", "Finds reliable websites.",
                                 "Filters duplicate links.", "Ranks search results.", "Returns verified resources."]),
        ("📖", "Reader Agent", ["Reads webpages.", "Extracts useful information.", "Removes HTML.",
                                 "Cleans text.", "Creates structured summaries."]),
        ("✍", "Writer Agent", ["Uses extracted knowledge.", "Generates a professional research report.",
                                "Creates sections and headings.", "Adds a conclusion.", "Produces references."]),
        ("🧠", "Critic Agent", ["Evaluates report quality.", "Detects weaknesses.",
                                 "Suggests improvements.", "Provides a final quality assessment."]),
    ]
 
    st.markdown('<div class="rf-ledger">', unsafe_allow_html=True)
    for i, (icon, title, points) in enumerate(steps, start=1):
        bullets = "".join(f"<li>{p}</li>" for p in points)
        st.markdown(
            f'<div class="rf-ledger-step" data-index="{i}"><div class="rf-card">'
            f'<div class="rf-feature-title">{icon} {title}</div>'
            f'<ul class="rf-feature-desc">{bullets}</ul></div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
 
 
def page_settings() -> None:
    st.markdown("## ⚙ Settings")
    st.markdown("#### Appearance")
    col1, col2 = st.columns(2)
    with col1:
        theme = st.selectbox("Theme", ["Dark", "Light"], index=["Dark", "Light"].index(st.session_state["theme"]))
    with col2:
        font_size = st.selectbox("Font size", ["Small", "Medium", "Large"],
                                  index=["Small", "Medium", "Large"].index(st.session_state["font_size"]))
    animations = st.toggle("Enable animations", value=st.session_state["animations"])
 
    if (theme, font_size, animations) != (st.session_state["theme"], st.session_state["font_size"], st.session_state["animations"]):
        st.session_state["theme"] = theme
        st.session_state["font_size"] = font_size
        st.session_state["animations"] = animations
        st.rerun()
 
    st.markdown('<hr class="rf-divider">', unsafe_allow_html=True)
    st.markdown("#### Data")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑 Clear Report History", use_container_width=True):
            st.session_state["reports"] = []
            st.session_state["current_run"] = None
            st.success("Report history cleared.")
    with col2:
        if st.button("♻ Reset Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
 

 
 
def page_about() -> None:
    st.markdown("## ℹ About ResearchFlow AI")
    st.markdown(
        "ResearchFlow AI is a next-generation Multi-Agent Research Assistant that automates "
        "the complete research workflow using autonomous AI agents. It searches trusted "
        "sources, extracts relevant information, generates comprehensive research reports, "
        "and critically evaluates the output to improve quality."
    )
 
    st.markdown('<hr class="rf-divider">', unsafe_allow_html=True)
    st.markdown('<div class="rf-section-eyebrow">Developer</div>', unsafe_allow_html=True)
 
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown(
            '<div style="width:96px;height:96px;border-radius:50%;'
            'background:linear-gradient(135deg,var(--rf-accent),var(--rf-teal));'
            'display:flex;align-items:center;justify-content:center;'
            'font-size:2.2rem;font-family:\'Fraunces\',serif;color:var(--rf-accent-ink);">AG</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown("#### Akash Goswami")
        st.markdown("**AI & Machine Learning Developer**")
        st.markdown(
            '"I am passionate about Artificial Intelligence, Machine Learning,RAG, Large '
            'Language Models, and Multi-Agent Systems. I enjoy building intelligent '
            'applications that solve real-world problems using modern AI technologies."'
        )
 
    st.markdown(
        """
        <div style="margin-top:1rem;">
            <a class="rf-social-link" href="https://github.com/akashgoswami139" target="_blank">🐙 GitHub</a>
            <a class="rf-social-link" href="https://www.linkedin.com/in/akashgoswami-/" target="_blank">💼 LinkedIn</a>
            <a class="rf-social-link" href="https://x.com/akashgoswami144" target="_blank">🐦 X (Twitter)</a>
            <a class="rf-social-link" href="https://mail.google.com/mail/?view=cm&fs=1&to=akashhgoswami26@gmail.com">📧 Email</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
 
 
# ============================================================================
# SIDEBAR / NAVIGATION
# ============================================================================
def render_sidebar() -> str:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding:0.5rem 0 1rem 0;">
                <div style="font-family:'Fraunces',serif;font-size:1.4rem;font-weight:700;">🧭 {APP_NAME}</div>
                <div style="font-family:'JetBrains Mono',monospace;font-size:0.72rem;
                text-transform:uppercase;letter-spacing:0.06em;color:var(--rf-teal);">{TAGLINE}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
 
        default_index = 0
        override = st.session_state.pop("_nav_override", None)
        if override in PAGES:
            default_index = PAGES.index(override)
 
        if HAS_OPTION_MENU:
            selected = option_menu(
                menu_title=None, options=PAGES, icons=PAGE_ICONS, default_index=default_index,
                styles={
                    "container": {"padding": "0", "background-color": "transparent"},
                    "icon": {"color": "var(--rf-accent)", "font-size": "16px"},
                    "nav-link": {"font-size": "14.5px", "text-align": "left", "margin": "2px 0", "border-radius": "10px"},
                    "nav-link-selected": {"background-color": "var(--rf-paper)"},
                },
            )
        else:
            selected = st.radio("Navigate", PAGES, index=default_index, label_visibility="collapsed")
 
        st.markdown('<hr class="rf-divider">', unsafe_allow_html=True)
        st.caption(f"Reports stored this session: {len(st.session_state['reports'])}")
        st.caption(datetime.now().strftime("%Y-%m-%d %H:%M"))
 
    return selected
 
 
# ============================================================================
# MAIN
# ============================================================================
def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🧭", layout="wide", initial_sidebar_state="expanded")
    init_session_state()
    inject_css()
 
    page = render_sidebar()
 
    if page == "Home":
        page_home()
    elif page == "Research":
        page_research()
    elif page == "Generated Reports":
        page_reports()
    elif page == "Working Process":
        page_working_process()
    elif page == "Settings":
        page_settings()
    elif page == "About":
        page_about()
 
 
if __name__ == "__main__":
    main()
 