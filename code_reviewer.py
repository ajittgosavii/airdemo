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

st.set_page_config(page_title="AI Code Reviewer", layout="wide")
st.title("AI Code Reviewer")
st.caption("Powered by Claude claude-sonnet-4-6")

with st.sidebar:
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...")

language = st.selectbox("Language", ["Python", "JavaScript", "Java", "Go", "SQL"])

# File uploader — populates the text area via session state
if "code_input" not in st.session_state:
    st.session_state["code_input"] = ""

uploaded_file = st.file_uploader(
    "Upload a code file", type=["py", "js", "java", "go", "sql"]
)
if uploaded_file is not None:
    st.session_state["code_input"] = uploaded_file.read().decode("utf-8")

code = st.text_area(
    "Paste your code here",
    height=400,
    placeholder="# Paste your code here...",
    key="code_input",
)

if st.button("Review My Code", type="primary"):
    if not api_key:
        st.warning("Please enter your Anthropic API key in the sidebar.")
    elif not code.strip():
        st.warning("Please paste or upload some code to review.")
    else:
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
                messages=[
                    {
                        "role": "user",
                        "content": f"Please review the following {language} code:\n\n```{language.lower()}\n{code}\n```",
                    }
                ],
            )

        tool_block = next(b for b in response.content if b.type == "tool_use")
        result = tool_block.input

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
