import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from src.config import (
    PROJECT_ROOT,
    ACCOUNTS,
    ACTIVE_ACCOUNT_NAME,
    DEFAULT_PROVIDER,
    API_MODE,
    BATCH_SIZE,
)
from src.auth import TikTokAuth
from src.uploader import TikTokUploader
from src.metadata_gen import generate_metadata, Metadata
from src.scanner import scan_content, ContentItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(tempfile.mkdtemp(prefix="tiktok_uploads_"))


def _save_uploaded_files(uploaded_files: list) -> int:
    saved = 0
    for f in uploaded_files:
        dest = UPLOAD_DIR / f.name
        dest.write_bytes(f.getbuffer())
        saved += 1
    return saved


def _run_scan():
    account = ACCOUNTS[get_wf()["account_name"]]
    items = scan_content(UPLOAD_DIR, account)

    wf = get_wf()
    wf["scanned_items"] = items
    wf["metadata_map"] = {}
    wf["approved_indices"] = []
    wf["current_batch"] = 0
    wf["upload_results"] = []

    valid = [i for i in items if not i.skip_reason and not i.already_uploaded]
    if valid:
        st.success(f"Found {len(valid)} new files to process.")
    else:
        st.warning("No new files to process.")


def _render_review_batch(items: list[ContentItem]):
    wf = get_wf()
    start = wf["current_batch"] * BATCH_SIZE
    end = min(start + BATCH_SIZE, len(items))
    batch = items[start:end]

    if not batch:
        if wf["approved_indices"]:
            st.success("All batches reviewed! Ready to upload.")
            _render_upload_button(items)
        return

    total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
    batch_num = wf["current_batch"] + 1

    st.subheader(f"Batch {batch_num} of {total_batches}")
    st.caption(f"Files {start + 1}-{end} of {len(items)}")

    needs_gen = [i for i in batch if i.file_path.name not in wf["metadata_map"]]
    if needs_gen:
        if st.button("Generate AI Captions for This Batch", type="primary"):
            account = ACCOUNTS[wf["account_name"]]
            with st.spinner("Generating captions..."):
                for item in needs_gen:
                    meta = generate_metadata(
                        item.file_path,
                        account.brand_context,
                        language=item.language,
                        provider=wf["provider"],
                    )
                    wf["metadata_map"][item.filename] = meta
            st.rerun()

    for i, item in enumerate(batch):
        idx = start + i
        meta = wf["metadata_map"].get(item.filename)

        with st.container(border=True):
            cols = st.columns([1, 3, 1])
            with cols[0]:
                icon = "VIDEO" if item.media_type == "video" else "IMAGE"
                lang_label = "AMHARIC" if item.language == "am" else "ENGLISH"
                st.markdown(f"**{icon}**")
                st.caption(f"{item.file_size_mb} MB | {lang_label}")

            with cols[1]:
                st.write(f"**{item.filename}**")
                if meta:
                    st.write(meta.caption)
                    tags = " ".join(t if t.startswith("#") else f"#{t}" for t in meta.hashtags)
                    st.caption(tags)
                else:
                    st.caption("Awaiting caption generation...")

            with cols[2]:
                if idx in wf["approved_indices"]:
                    st.success("APPROVED")
                else:
                    if st.button("Approve", key=f"approve_{idx}", use_container_width=True):
                        if idx not in wf["approved_indices"]:
                            wf["approved_indices"].append(idx)
                        st.rerun()

    meta_for_all = all(item.filename in wf["metadata_map"] for item in batch)
    if meta_for_all:
        cols = st.columns([1, 1, 2])
        with cols[0]:
            if st.button("Approve All in Batch", type="primary", use_container_width=True):
                for j in range(start, end):
                    if j not in wf["approved_indices"]:
                        wf["approved_indices"].append(j)
                st.rerun()
        with cols[1]:
            if st.button("Next Batch", use_container_width=True):
                wf["current_batch"] += 1
                st.rerun()

    if wf["approved_indices"]:
        st.divider()
        _render_upload_button(items)


def _render_upload_button(all_items: list[ContentItem]):
    wf = get_wf()
    approved = [all_items[i] for i in wf["approved_indices"] if i < len(all_items)]

    missing_meta = [i for i in approved if i.filename not in wf["metadata_map"]]
    if missing_meta:
        st.warning(f"{len(missing_meta)} approved items missing captions - generate first.")
        return

    if st.button("Upload Approved Posts", type="primary", use_container_width=True):
        account = ACCOUNTS[wf["account_name"]]
        auth = TikTokAuth(account)
        uploader = TikTokUploader(auth, account)

        progress_bar = st.progress(0, text="Uploading...")
        status_placeholder = st.empty()

        consecutive_failures = 0
        results = []

        for i, item in enumerate(approved):
            meta = wf["metadata_map"][item.filename]
            status_placeholder.info(f"Uploading {item.filename} ({i + 1}/{len(approved)})...")
            progress_bar.progress((i) / len(approved), text=f"{i + 1}/{len(approved)}")

            attempt = 1
            while attempt <= 2:
                try:
                    if item.media_type == "video":
                        result = uploader.upload_video(item.file_path, meta.caption, meta.hashtags)
                    else:
                        result = uploader.upload_photo(item.file_path, meta.caption, meta.hashtags)

                    result["status_label"] = "UPLOADED" if attempt == 1 else "UPLOADED_RETRY"
                    result["attempt"] = attempt
                    result["error"] = None
                    consecutive_failures = 0
                    break

                except Exception as e:
                    if attempt == 1:
                        status_placeholder.warning(f"Retrying {item.filename} after error: {e}")
                        import time
                        time.sleep(10)
                        attempt += 1
                    else:
                        result = {
                            "file": item.filename,
                            "status": "FAILED",
                            "status_label": "FAILED",
                            "attempt": attempt,
                            "error": str(e),
                        }
                        consecutive_failures += 1
                        break

            results.append(result)
            _write_log(account.name, item, meta, result)

            if consecutive_failures >= 2:
                status_placeholder.error("2 consecutive failures - stopping.")
                break

        progress_bar.progress(1.0, text="Done!")
        wf["upload_results"] = results

        success = sum(1 for r in results if r.get("status") == "SEND_TO_USER_INBOX")
        status_placeholder.success(f"Done! {success}/{len(results)} uploaded successfully.")
        st.rerun()


def _write_log(account_name: str, item: ContentItem, meta: Metadata, result: dict):
    log_path = PROJECT_ROOT / "logs" / "upload_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brand": account_name,
        "filename": item.filename,
        "status": result.get("status_label", "UNKNOWN"),
        "publish_id": result.get("publish_id"),
        "caption": meta.caption[:100],
        "hashtags": meta.hashtags,
        "file_size_mb": item.file_size_mb,
        "attempt": result.get("attempt", 1),
        "error_code": None,
        "error_message": result.get("error"),
        "provider_used": get_wf()["provider"],
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def get_wf():
    return st.session_state.workflow


st.set_page_config(
    page_title="TikTok Uploader",
    page_icon=":notes:",
    layout="wide",
)

st.title("TikTok Bulk Uploader")
st.caption("Scan folder -> generate captions -> approve -> upload as inbox drafts")

ACCOUNT_NAMES = list(ACCOUNTS.keys())

if "workflow" not in st.session_state:
    st.session_state.workflow = {
        "account_name": ACTIVE_ACCOUNT_NAME,
        "provider": DEFAULT_PROVIDER,
        "scanned_items": [],
        "metadata_map": {},
        "approved_indices": [],
        "current_batch": 0,
        "upload_results": [],
        "log_entries": [],
    }

wf = get_wf()

with st.sidebar:
    st.header("Settings")

    wf["account_name"] = st.selectbox("Account", ACCOUNT_NAMES, index=ACCOUNT_NAMES.index(wf["account_name"]))

    wf["provider"] = st.selectbox(
        "AI Provider",
        ["gemini", "openai", "claude", "ollama"],
        index=["gemini", "openai", "claude", "ollama"].index(wf["provider"]),
    )

    st.info(f"API Mode: **{API_MODE.upper()}**")

    uploaded_files = st.file_uploader(
        "Upload images/videos",
        type=["mp4", "mov", "jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded_files:
        count = _save_uploaded_files(uploaded_files)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Scan Uploads", use_container_width=True):
            _run_scan()
    with col2:
        if st.button("Reset All", use_container_width=True):
            st.session_state.workflow = {
                "account_name": ACTIVE_ACCOUNT_NAME,
                "provider": DEFAULT_PROVIDER,
                "scanned_items": [],
                "metadata_map": {},
                "approved_indices": [],
                "current_batch": 0,
                "upload_results": [],
                "log_entries": [],
            }
            st.rerun()

    st.divider()
    st.metric("Files found", len([i for i in wf["scanned_items"] if not i.skip_reason]))
    st.metric("Already uploaded", len([i for i in wf["scanned_items"] if i.already_uploaded]))
    st.metric("Approved", len(wf["approved_indices"]))
    st.metric("Uploaded", len([r for r in wf["upload_results"] if r.get("status") == "SEND_TO_USER_INBOX"]))

tab1, tab2 = st.tabs(["Scan & Review", "Upload Log"])

with tab1:
    valid_items = [i for i in wf["scanned_items"] if not i.skip_reason and not i.already_uploaded]
    skipped_items = [i for i in wf["scanned_items"] if i.skip_reason or i.already_uploaded]

    if not valid_items and not skipped_items:
        if wf["scanned_items"]:
            st.warning("All content has already been uploaded or skipped.")
        else:
            st.info("Upload files in the sidebar and click **Scan Uploads**.")
    else:
        if skipped_items:
            with st.expander(f"Skipped ({len(skipped_items)} files)"):
                for item in skipped_items:
                    reason = item.skip_reason or "Already uploaded"
                    st.caption(f"[SKIP] {item.filename} - {reason}")

        if valid_items:
            _render_review_batch(valid_items)

    if wf["upload_results"]:
        st.divider()
        st.subheader("Upload Results")
        for r in wf["upload_results"]:
            status_icon = "OK" if r.get("status") == "SEND_TO_USER_INBOX" else "FAIL"
            st.write(f"[{status_icon}] {r.get('file', '?')} - {r.get('status', '?')}")
            if r.get("error"):
                st.caption(f"  Error: {r['error']}")

with tab2:
    log_path = PROJECT_ROOT / "logs" / "upload_log.jsonl"
    if log_path.exists():
        log_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
        st.text_area("Raw log", "\n".join(log_lines[-50:]), height=400)
    else:
        st.info("No log entries yet.")
