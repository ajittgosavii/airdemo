import anthropic
import streamlit as st

REVIEW_TOOL = {
    "name": "code_review",
    "description": "Return a structured code review with bugs, security issues, performance issues, and a summary.",
    "input_schema": {
        "type": "object",
        "properties": {
            "bugs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line":        {"type": "integer"},
                        "description": {"type": "string"},
                        "severity":    {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    },
                    "required": ["line", "description", "severity"],
                    "additionalProperties": False,
                },
            },
            "security": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line":        {"type": "integer"},
                        "description": {"type": "string"},
                        "severity":    {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    },
                    "required": ["line", "description", "severity"],
                    "additionalProperties": False,
                },
            },
            "performance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "line":        {"type": "integer"},
                        "description": {"type": "string"},
                    },
                    "required": ["line", "description"],
                    "additionalProperties": False,
                },
            },
            "summary": {"type": "string"},
        },
        "required": ["bugs", "security", "performance", "summary"],
        "additionalProperties": False,
    },
}

SEVERITY_BADGE = {
    "HIGH":   '<span style="background:#dc2626;color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600">HIGH</span>',
    "MEDIUM": '<span style="background:#ea580c;color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600">MEDIUM</span>',
    "LOW":    '<span style="background:#2563eb;color:white;padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600">LOW</span>',
}

# ── PAGE SETUP ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="AI Code Reviewer", layout="wide")
st.title("AI Code Reviewer")
st.caption("Powered by Claude claude-sonnet-4-6")

_secret_key = st.secrets.get("ANTHROPIC_API_KEY", "")
with st.sidebar:
    api_key = st.text_input(
        "Anthropic API Key",
        value=_secret_key,
        type="password",
        placeholder="sk-ant-...",
        help="Or set ANTHROPIC_API_KEY in Streamlit Cloud secrets.",
    )

# ── FIX EXECUTION (right after api_key is available, before any other widget) ─
# The on_click callback stores everything needed so this block runs at the
# top of the script and the results section (Fix Now button) is NEVER reached.
if st.session_state.get("do_fix"):
    _key      = st.session_state.pop("_fix_api_key", api_key)
    _result   = st.session_state.pop("_fix_result", {})
    _src_code = st.session_state.pop("_fix_code", "")
    _src_lang = st.session_state.pop("_fix_lang", "Python")
    st.session_state.pop("do_fix", None)

    _issues = []
    for item in _result.get("bugs", []):
        _issues.append(f"- Bug (line {item['line']}, {item['severity']}): {item['description']}")
    for item in _result.get("security", []):
        _issues.append(f"- Security (line {item['line']}, {item['severity']}): {item['description']}")
    for item in _result.get("performance", []):
        _issues.append(f"- Performance (line {item['line']}): {item['description']}")

    st.markdown("### 🔧 Fixed Code")
    st.caption("Streaming fix from Claude…")
    _placeholder = st.empty()
    _accumulated = ""

    with anthropic.Anthropic(api_key=_key).messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "You are an expert software engineer. Fix only the issues listed. "
            "Return the complete corrected source file and nothing else — "
            "no explanations, no markdown fences, no commentary."
        ),
        messages=[{
            "role": "user",
            "content": (
                f"Fix the following issues in this {_src_lang} code:\n\n"
                + "\n".join(_issues)
                + f"\n\nOriginal code:\n\n{_src_code}"
            ),
        }],
    ) as _stream:
        for _token in _stream.text_stream:
            _accumulated += _token
            _placeholder.code(_accumulated, language=_src_lang.lower())

    st.session_state["pending_fix"] = _accumulated
    st.success("✅ Fix applied — editor updated.")
    st.rerun()  # script stops here; next run applies pending_fix and skips results

# ── REST OF NORMAL FLOW ───────────────────────────────────────────────────────
language = st.selectbox("Language", ["Python", "JavaScript", "Java", "Go", "SQL"])

# Apply any pending fix before the key-bound widget renders
if "pending_fix" in st.session_state:
    st.session_state["code_input"] = st.session_state.pop("pending_fix")

if "code_input" not in st.session_state:
    st.session_state["code_input"] = ""

uploaded_file = st.file_uploader("Upload a code file", type=["py", "js", "java", "go", "sql"])
if uploaded_file is not None:
    st.session_state["code_input"] = uploaded_file.read().decode("utf-8")

code = st.text_area(
    "Paste your code here",
    height=400,
    placeholder="# Paste your code here...",
    key="code_input",
)

# ── REVIEW ────────────────────────────────────────────────────────────────────
if st.button("Review My Code", type="primary"):
    if not api_key:
        st.warning("Please enter your Anthropic API key in the sidebar.")
    elif not code.strip():
        st.warning("Please paste or upload some code to review.")
    else:
        for k in ("review_result", "reviewed_code", "reviewed_language"):
            st.session_state.pop(k, None)

        client = anthropic.Anthropic(api_key=api_key)
        with st.spinner("Reviewing your code..."):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=(
                    "You are a senior code reviewer. Review the provided code for bugs, "
                    "security vulnerabilities, performance issues, and code quality. "
                    "Be specific with line references where possible."
                ),
                tools=[REVIEW_TOOL],
                tool_choice={"type": "tool", "name": "code_review"},
                messages=[{
                    "role": "user",
                    "content": f"Please review the following {language} code:\n\n```{language.lower()}\n{code}\n```",
                }],
            )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        st.session_state["review_result"]     = tool_block.input
        st.session_state["reviewed_code"]     = code
        st.session_state["reviewed_language"] = language
        st.rerun()

# ── RENDER RESULTS ────────────────────────────────────────────────────────────
if "review_result" in st.session_state:
    result = st.session_state["review_result"]

    with st.expander("✅ Summary", expanded=True):
        st.write(result["summary"])

    bugs = result["bugs"]
    with st.expander(f"🐛 Bugs ({len(bugs)})", expanded=bool(bugs)):
        if bugs:
            for item in bugs:
                st.markdown(
                    f"- {SEVERITY_BADGE[item['severity']]} "
                    f"&nbsp;Line {item['line']}: {item['description']}",
                    unsafe_allow_html=True,
                )
        else:
            st.write("No bugs found.")

    security = result["security"]
    with st.expander(f"🔒 Security ({len(security)})", expanded=bool(security)):
        if security:
            for item in security:
                st.markdown(
                    f"- {SEVERITY_BADGE[item['severity']]} "
                    f"&nbsp;Line {item['line']}: {item['description']}",
                    unsafe_allow_html=True,
                )
        else:
            st.write("No security issues found.")

    performance = result["performance"]
    with st.expander(f"⚡ Performance ({len(performance)})", expanded=bool(performance)):
        if performance:
            for item in performance:
                st.markdown(f"- Line {item['line']}: {item['description']}")
        else:
            st.write("No performance issues found.")

    if bugs or security or performance:
        st.divider()

        def _on_fix_click():
            """Snapshot everything into session state so do_fix block at top can run independently."""
            st.session_state["do_fix"]        = True
            st.session_state["_fix_api_key"]  = api_key
            st.session_state["_fix_result"]   = st.session_state.get("review_result", {})
            st.session_state["_fix_code"]     = st.session_state.get("reviewed_code", "")
            st.session_state["_fix_lang"]     = st.session_state.get("reviewed_language", "Python")
            # Clear review state in the callback so it's gone on the next render
            for k in ("review_result", "reviewed_code", "reviewed_language"):
                st.session_state.pop(k, None)

        def _on_clear_click():
            for k in ("review_result", "reviewed_code", "reviewed_language"):
                st.session_state.pop(k, None)

        col1, col2 = st.columns([1, 1])
        with col1:
            st.button("🔧 Fix Now", type="primary", on_click=_on_fix_click, use_container_width=True)
        with col2:
            st.button("🗑️ Clear Review", on_click=_on_clear_click, use_container_width=True)
