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

def _trigger_fix():
    st.session_state["do_fix"] = True

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

language = st.selectbox("Language", ["Python", "JavaScript", "Java", "Go", "SQL"])

# Phase 1: apply any pending fix before the widget renders
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
        # Clear any previous review so Fix Now cannot linger
        for k in ("review_result", "reviewed_code", "reviewed_language", "do_fix"):
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
        st.session_state["review_result"]    = tool_block.input
        st.session_state["reviewed_code"]    = code
        st.session_state["reviewed_language"] = language
        st.rerun()

# ── FIX (runs before results render so Fix Now button never shows on fix rerun) ─
if st.session_state.get("do_fix"):
    _result  = st.session_state.get("review_result", {})
    src_code = st.session_state.get("reviewed_code", "")
    src_lang = st.session_state.get("reviewed_language", "Python")

    _bugs        = _result.get("bugs", [])
    _security    = _result.get("security", [])
    _performance = _result.get("performance", [])

    issues = []
    for item in _bugs:
        issues.append(f"- Bug (line {item['line']}, {item['severity']}): {item['description']}")
    for item in _security:
        issues.append(f"- Security (line {item['line']}, {item['severity']}): {item['description']}")
    for item in _performance:
        issues.append(f"- Performance (line {item['line']}): {item['description']}")

    # Clear all review state before streaming
    for k in ("do_fix", "review_result", "reviewed_code", "reviewed_language"):
        st.session_state.pop(k, None)

    client = anthropic.Anthropic(api_key=api_key)
    st.markdown("### 🔧 Fixed Code")
    st.caption("Streaming fix from Claude…")
    placeholder = st.empty()
    accumulated = ""

    with client.messages.stream(
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
                f"Fix the following issues in this {src_lang} code:\n\n"
                + "\n".join(issues)
                + f"\n\nOriginal code:\n\n{src_code}"
            ),
        }],
    ) as stream:
        for token in stream.text_stream:
            accumulated += token
            placeholder.code(accumulated, language=src_lang.lower())

    st.session_state["pending_fix"] = accumulated
    st.success("✅ Fix applied — editor updated.")
    st.rerun()

# ── RENDER RESULTS (always from session state) ─────────────────────────────
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
        col1, col2 = st.columns([1, 1])
        with col1:
            st.button("🔧 Fix Now", type="primary", on_click=_trigger_fix, use_container_width=True)
        with col2:
            if st.button("🗑️ Clear Review", use_container_width=True):
                for k in ("review_result", "reviewed_code", "reviewed_language", "do_fix"):
                    st.session_state.pop(k, None)
                st.rerun()
