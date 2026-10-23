"""Streamlit UI of the document assistant. One page: upload, documents, ask."""

import streamlit as st
from api_client import ApiClient, ApiError

POLL_INTERVAL = "3s"
ACTIVE_STATUSES = {"uploaded", "processing"}
DOCUMENTS_SHOWN = 50
STATUS_LABELS = {
    "uploaded": "uploaded (waiting)",
    "processing": "processing...",
    "processed": "processed",
    "failed": "failed",
}
NOT_FOUND_TEXT = "Not found: the documents do not answer this question."


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def upload_section(client: ApiClient) -> None:
    st.subheader("1. Upload a PDF")
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash)

    number = st.session_state.get("uploader_n", 0)
    file = st.file_uploader("PDF file", type=["pdf"], key=f"uploader_{number}")
    if file is not None and st.button("Upload"):
        try:
            with st.spinner("Uploading..."):
                document = client.upload_document(file.name, file.getvalue())
        except ApiError as error:
            st.error(str(error))
            return
        st.session_state["uploader_n"] = number + 1  # a new key empties the picker
        st.session_state["has_active"] = True  # start the status polling
        st.session_state["flash"] = (
            f"Uploaded {document['filename']}. Processing starts within about a minute."
        )
        st.rerun()


def documents_section(client: ApiClient) -> None:
    st.subheader("2. Documents")
    # The fragment refreshes itself only while a document is waiting or processing.
    run_every = POLL_INTERVAL if st.session_state.get("has_active", True) else None

    @st.fragment(run_every=run_every)
    def panel() -> None:
        try:
            page = client.list_documents(limit=DOCUMENTS_SHOWN)
        except ApiError as error:
            st.error(str(error))
            return

        items = page["items"]
        if items:
            st.dataframe(
                [
                    {
                        "File": d["filename"],
                        "Status": STATUS_LABELS.get(d["status"], d["status"]),
                        "Uploaded": d["created_at"][:16].replace("T", " "),
                    }
                    for d in items
                ],
                hide_index=True,
            )
            if page["total"] > len(items):
                st.caption(f"Showing the newest {len(items)} of {page['total']} documents.")
            if any(d["status"] == "failed" for d in items):
                st.warning(
                    "Some documents failed to process. "
                    "Ask the administrator to check the processing log."
                )
        else:
            st.info("No documents yet.")

        active = any(d["status"] in ACTIVE_STATUSES for d in items)
        if st.session_state.get("has_active") != active:
            st.session_state["has_active"] = active
            st.rerun()  # full rerun, so run_every is decided again

    panel()


MODEL_POLL_READY = "30s"  # slow check once ready: it notices an API restart
MODEL_MESSAGES = {
    "ready": "Model: ready.",
    "loading": "Model: loading. Questions wait until it is ready (up to a minute)...",
    "idle": "Model: not loaded yet. The first question will load it (up to a minute).",
    "unknown": "Model: status unknown. Is the API running?",
}


def model_status_section(client: ApiClient) -> None:
    ready = st.session_state.get("model_ready", False)
    run_every = MODEL_POLL_READY if ready else POLL_INTERVAL

    @st.fragment(run_every=run_every)
    def status_line() -> None:
        status = client.model_status()
        st.caption(MODEL_MESSAGES.get(status, MODEL_MESSAGES["unknown"]))
        now_ready = status == "ready"
        if st.session_state.get("model_ready", False) != now_ready:
            st.session_state["model_ready"] = now_ready
            st.rerun()  # full rerun, so run_every is decided again

    status_line()


def render_answer(result: dict) -> None:
    if not result["found"]:
        st.warning(result["answer"] or NOT_FOUND_TEXT)
        return
    st.markdown(result["answer"])
    st.markdown("**Sources**")
    for citation in result["citations"]:
        pages = ", ".join(str(p) for p in citation["page_numbers"])
        label = f"{citation['filename']} (page {pages})"
        if citation["heading"]:
            label += f" - {citation['heading']}"
        with st.expander(label):
            st.write(citation["text"])


def ask_section(client: ApiClient) -> None:
    st.subheader("3. Ask a question")
    # A form sends the question only on submit (the button or Ctrl+Enter), so the
    # button needs no "disabled" state waiting for the text box to lose focus.
    with st.form("ask_form", border=False):
        question = st.text_area("Your question", height=100)
        with st.expander("Advanced"):
            # The API enforces the real limits; empty means the server default.
            top_k = st.number_input(
                "Chunks retrieved (top_k), empty = default",
                min_value=1,
                max_value=20,
                value=None,
            )
        submitted = st.form_submit_button("Ask")

    if submitted:
        if not question.strip():
            st.warning("Type a question first.")
        else:
            try:
                with st.spinner(
                    "Searching the documents... "
                    "the first question after a server start can take up to a minute."
                ):
                    result = client.ask(question.strip(), int(top_k) if top_k else None)
            except ApiError as error:
                st.session_state.pop("answer", None)
                st.error(str(error))
                return
            st.session_state["answer"] = result

    if "answer" in st.session_state:
        render_answer(st.session_state["answer"])


st.set_page_config(page_title="Document assistant", layout="wide")
st.title("Document assistant")
_client = get_client()
model_status_section(_client)
upload_section(_client)
documents_section(_client)
ask_section(_client)
