"""
ui.py
Streamlit frontend for the Codebase AI Assistant.
Run with: streamlit run ui.py
"""

import streamlit as st
import requests
import time

# ── Config ─────────────────────────────────────────────────────────────────────
import os
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

st.set_page_config(
    page_title="Codebase AI Assistant",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Sora:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Sora', sans-serif;
    }

    /* Dark sidebar */
    [data-testid="stSidebar"] {
        background: #0d1117;
        border-right: 1px solid #21262d;
    }
    [data-testid="stSidebar"] * {
        color: #c9d1d9 !important;
    }

    /* Main background */
    .stApp {
        background: #0d1117;
        color: #c9d1d9;
    }

    /* Cards */
    .card {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }

    .card-green {
        border-left: 4px solid #3fb950;
    }

    .card-blue {
        border-left: 4px solid #58a6ff;
    }

    .card-purple {
        border-left: 4px solid #bc8cff;
    }

    /* Source badge */
    .source-badge {
        display: inline-block;
        background: #21262d;
        border: 1px solid #30363d;
        border-radius: 6px;
        padding: 2px 10px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        color: #8b949e;
        margin: 3px 3px 3px 0;
    }

    /* Stat box */
    .stat-box {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        color: #58a6ff;
        font-family: 'JetBrains Mono', monospace;
    }
    .stat-label {
        font-size: 0.75rem;
        color: #8b949e;
        margin-top: 4px;
    }

    /* Chat bubble - user */
    .chat-user {
        background: #1f6feb22;
        border: 1px solid #1f6feb44;
        border-radius: 12px 12px 2px 12px;
        padding: 12px 16px;
        margin: 8px 0;
        margin-left: 20%;
        color: #c9d1d9;
    }

    /* Chat bubble - assistant */
    .chat-assistant {
        background: #161b22;
        border: 1px solid #21262d;
        border-radius: 12px 12px 12px 2px;
        padding: 12px 16px;
        margin: 8px 0;
        margin-right: 10%;
        color: #c9d1d9;
    }

    .chat-label {
        font-size: 0.7rem;
        color: #8b949e;
        margin-bottom: 6px;
        font-family: 'JetBrains Mono', monospace;
    }

    /* Headings */
    h1, h2, h3 { color: #e6edf3 !important; }

    /* Input fields */
    .stTextInput input, .stTextArea textarea {
        background: #161b22 !important;
        border: 1px solid #30363d !important;
        color: #c9d1d9 !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* Buttons */
    .stButton button {
        background: #238636 !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-family: 'Sora', sans-serif !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        transition: background 0.2s;
    }
    .stButton button:hover {
        background: #2ea043 !important;
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab"] {
        font-family: 'Sora', sans-serif;
        color: #8b949e;
    }
    .stTabs [aria-selected="true"] {
        color: #58a6ff !important;
        border-bottom-color: #58a6ff !important;
    }

    /* Hide default streamlit branding */
    #MainMenu, footer { visibility: hidden; }

    /* Logo text */
    .logo {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.1rem;
        font-weight: 600;
        color: #58a6ff;
        letter-spacing: -0.5px;
    }

    .logo span {
        color: #3fb950;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ────────────────────────────────────────────────────────────

def check_api_health():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def ingest_github(github_url: str, reindex: bool, include_git: bool):
    try:
        r = requests.post(
            f"{API_BASE}/ingest/github",
            json={
                "github_url": github_url,
                "reindex": reindex,
                "include_git_history": include_git,
            },
            timeout=600,  # cloning + indexing can take time
        )
        return r.json(), r.status_code
    except requests.exceptions.Timeout:
        return {"detail": "Request timed out. Large repos take time — check backend logs."}, 408
    except Exception as e:
        return {"detail": str(e)}, 500


def ask_question(repo_name: str, query: str, top_k: int, history: list):
    try:
        r = requests.post(
            f"{API_BASE}/ask",
            json={
                "repo_name": repo_name,
                "query": query,
                "top_k": top_k,
                "conversation_history": history,
            },
            timeout=60,
        )
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500


def generate_docs(repo_name: str, file_path: str):
    try:
        r = requests.post(
            f"{API_BASE}/document",
            json={"repo_name": repo_name, "file_path": file_path},
            timeout=60,
        )
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500


def get_status(repo_name: str):
    try:
        r = requests.get(f"{API_BASE}/status/{repo_name}", timeout=5)
        return r.json(), r.status_code
    except Exception as e:
        return {"detail": str(e)}, 500


# ── Session state ───────────────────────────────────────────────────────────────
if "indexed_repo" not in st.session_state:
    st.session_state.indexed_repo = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "index_stats" not in st.session_state:
    st.session_state.index_stats = None


# ── Sidebar ─────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="logo">code<span>brain</span>.ai</div>', unsafe_allow_html=True)
    st.markdown("---")

    # API Health
    is_healthy = check_api_health()
    status_color = "🟢" if is_healthy else "🔴"
    st.markdown(f"{status_color} **API:** {'Connected' if is_healthy else 'Offline — start docker-compose'}")
    st.markdown("---")

    # Active repo
    if st.session_state.indexed_repo:
        st.markdown("**📦 Active Repo**")
        st.code(st.session_state.indexed_repo, language=None)
        if st.session_state.index_stats:
            stats = st.session_state.index_stats
            st.markdown(f"Chunks indexed: **{stats.get('total_chunks', '?')}**")

        if st.button("🔄 Switch Repo"):
            st.session_state.indexed_repo = None
            st.session_state.chat_history = []
            st.session_state.index_stats = None
            st.rerun()
        st.markdown("---")

    # Settings
    st.markdown("**⚙️ Settings**")
    top_k = st.slider("Context chunks (top_k)", min_value=1, max_value=12, value=5)
    include_git = st.toggle("Include git history", value=True)

    st.markdown("---")
    st.markdown(
        "<small style='color:#8b949e'>Built for ET Gen AI Hackathon<br/>Powered by OpenAI + ChromaDB</small>",
        unsafe_allow_html=True
    )


# ── Main content ────────────────────────────────────────────────────────────────
st.markdown("## 🧠 Codebase AI Assistant")
st.markdown(
    "<p style='color:#8b949e'>Index any GitHub repository and chat with your codebase in natural language.</p>",
    unsafe_allow_html=True
)

if not is_healthy:
    st.error("⚠️ Backend API is not running. Please start it with `docker-compose up --build` and refresh.")
    st.stop()


# ── TABS ────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🚀  Index Repo", "💬  Chat", "📄  Generate Docs"])


# ──────────────────────────────────────────────────────────────────────────────
# TAB 1: Index a GitHub Repo
# ──────────────────────────────────────────────────────────────────────────────
with tab1:
    st.markdown("### Index a GitHub Repository")
    st.markdown(
        "<p style='color:#8b949e'>Paste any public GitHub URL. The assistant will clone it, parse all source files and git history, and build a searchable knowledge base.</p>",
        unsafe_allow_html=True
    )

    github_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/tiangolo/fastapi",
        label_visibility="collapsed",
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        reindex = st.checkbox("Force re-index", value=False)
    with col2:
        st.markdown(
            "<small style='color:#8b949e'>Check this if you want to wipe and rebuild the index from scratch.</small>",
            unsafe_allow_html=True
        )

    if st.button("⚡ Index Repository", use_container_width=True):
        if not github_url.strip():
            st.warning("Please enter a GitHub URL.")
        else:
            with st.spinner("Cloning and indexing repository... this may take 1–3 minutes ⏳"):
                result, status_code = ingest_github(github_url.strip(), reindex, include_git)

            if status_code == 200:
                st.session_state.indexed_repo = result.get("repo_name")
                st.session_state.chat_history = []
                st.session_state.index_stats = {
                    "total_chunks": result.get("total_in_collection")
                }
                st.success(f"✅ Repository indexed successfully!")

                # Stats
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.markdown(f"""
                        <div class="stat-box">
                            <div class="stat-number">{result.get('files_loaded', 0)}</div>
                            <div class="stat-label">Files Loaded</div>
                        </div>""", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"""
                        <div class="stat-box">
                            <div class="stat-number">{result.get('file_chunks', 0)}</div>
                            <div class="stat-label">Code Chunks</div>
                        </div>""", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"""
                        <div class="stat-box">
                            <div class="stat-number">{result.get('git_chunks', 0)}</div>
                            <div class="stat-label">Git Commits</div>
                        </div>""", unsafe_allow_html=True)
                with c4:
                    st.markdown(f"""
                        <div class="stat-box">
                            <div class="stat-number">{result.get('total_in_collection', 0)}</div>
                            <div class="stat-label">Total Indexed</div>
                        </div>""", unsafe_allow_html=True)

                st.markdown("---")
                st.info("👉 Switch to the **Chat** tab to start asking questions!")
            else:
                err = result.get("detail", "Unknown error")
                st.error(f"❌ Indexing failed: {err}")


# ──────────────────────────────────────────────────────────────────────────────
# TAB 2: Chat with the Codebase
# ──────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("### Chat with Your Codebase")

    if not st.session_state.indexed_repo:
        st.info("👈 First index a repository in the **Index Repo** tab.")
    else:
        st.markdown(
            f"<p style='color:#8b949e'>Asking about: <code>{st.session_state.indexed_repo}</code></p>",
            unsafe_allow_html=True
        )

        # Suggested questions
        st.markdown("**💡 Try asking:**")
        suggestions = [
            "How does authentication work?",
            "What does the main entry point do?",
            "What were the most recent changes?",
            "Explain the folder structure",
            "Which files handle database operations?",
        ]
        cols = st.columns(len(suggestions))
        for i, sug in enumerate(suggestions):
            with cols[i]:
                if st.button(sug, key=f"sug_{i}", use_container_width=True):
                    st.session_state["prefill_query"] = sug

        st.markdown("---")

        # Chat history display
        if st.session_state.chat_history:
            for turn in st.session_state.chat_history:
                if turn["role"] == "user":
                    st.markdown(f"""
                        <div class="chat-user">
                            <div class="chat-label">YOU</div>
                            {turn["content"]}
                        </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="chat-assistant">
                            <div class="chat-label">🧠 ASSISTANT</div>
                            {turn["content"]}
                        </div>""", unsafe_allow_html=True)
                    if turn.get("sources"):
                        badges = "".join([f'<span class="source-badge">{s}</span>' for s in turn["sources"]])
                        st.markdown(f"<div style='margin-left:4px'>{badges}</div>", unsafe_allow_html=True)
            st.markdown("")

        # Input box
        prefill = st.session_state.pop("prefill_query", "")
        query = st.text_input(
            "Ask a question...",
            value=prefill,
            placeholder="e.g. How does the routing system work?",
            label_visibility="collapsed",
            key="chat_input"
        )

        col_send, col_clear = st.columns([5, 1])
        with col_send:
            send = st.button("Send →", use_container_width=True)
        with col_clear:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()

        if send and query.strip():
            # Build conversation history for multi-turn (last 6 messages only)
            history_payload = [
                {"role": t["role"], "content": t["content"]}
                for t in st.session_state.chat_history[-6:]
            ]

            with st.spinner("Thinking..."):
                result, status_code = ask_question(
                    st.session_state.indexed_repo,
                    query.strip(),
                    top_k,
                    history_payload,
                )

            if status_code == 200:
                st.session_state.chat_history.append({"role": "user", "content": query.strip()})
                st.session_state.chat_history.append({
                    "role": "assistant",
                    "content": result.get("answer", ""),
                    "sources": result.get("sources", []),
                })
                st.rerun()
            else:
                st.error(f"❌ Error: {result.get('detail', 'Unknown error')}")


# ──────────────────────────────────────────────────────────────────────────────
# TAB 3: Generate Documentation
# ──────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("### Auto-Generate File Documentation")
    st.markdown(
        "<p style='color:#8b949e'>Enter a file path from the indexed repo and get AI-generated documentation for it.</p>",
        unsafe_allow_html=True
    )

    if not st.session_state.indexed_repo:
        st.info("👈 First index a repository in the **Index Repo** tab.")
    else:
        st.markdown(
            f"<p style='color:#8b949e'>Repo: <code>{st.session_state.indexed_repo}</code></p>",
            unsafe_allow_html=True
        )

        file_path = st.text_input(
            "File path (relative to repo root)",
            placeholder="e.g. src/auth/login.py or README.md",
            label_visibility="collapsed",
        )

        if st.button("📝 Generate Documentation", use_container_width=True):
            if not file_path.strip():
                st.warning("Please enter a file path.")
            else:
                with st.spinner("Generating documentation..."):
                    result, status_code = generate_docs(
                        st.session_state.indexed_repo,
                        file_path.strip()
                    )

                if status_code == 200:
                    st.success(f"✅ Documentation generated for `{file_path}`")
                    st.markdown("---")

                    doc_text = result.get("documentation", "")
                    st.markdown(doc_text)

                    st.markdown("---")
                    st.download_button(
                        label="⬇️ Download as Markdown",
                        data=doc_text,
                        file_name=f"{file_path.replace('/', '_')}_docs.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
                else:
                    st.error(f"❌ Error: {result.get('detail', 'Unknown error')}")