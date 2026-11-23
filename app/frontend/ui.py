import os
import uuid
import requests
import streamlit as st

API_URL = os.getenv("DOCLOCALAI_API_URL", "http://doclocalai-api:8000")
APP_TITLE = os.getenv("APP_TITLE", "DocLocalAI — Runbook Assistant")
APP_PAGE_TITLE = os.getenv("APP_PAGE_TITLE", "DocLocalAI Assistant")

st.set_page_config(
    page_title=APP_PAGE_TITLE,
    layout="wide",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)
st.title(APP_TITLE)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None
if "confirm_delete_all" not in st.session_state:
    st.session_state.confirm_delete_all = False
if "view_runbook" not in st.session_state:
    st.session_state.view_runbook = None
if "upload_counter" not in st.session_state:
    st.session_state.upload_counter = 0
if "show_prompt_editor" not in st.session_state:
    st.session_state.show_prompt_editor = False
if "edit_prompt_id" not in st.session_state:
    st.session_state.edit_prompt_id = None

with st.sidebar:
    # Runbook Management Section
    with st.expander("📚 Manage Runbooks", expanded=False):
        st.caption("Upload and manage knowledge base")
        st.caption("⚠️ Max file size: 2 MB | Formats: .md, .txt")

        # File uploader (key changes after each upload to reset it)
        uploaded_file = st.file_uploader(
            "Upload Runbook",
            type=["md", "txt"],
            help="Upload markdown or text files (max 2MB)",
            key=f"runbook_uploader_{st.session_state.upload_counter}"
        )

        if uploaded_file is not None:
            # Show file info
            file_size_mb = uploaded_file.size / (1024 * 1024)
            if file_size_mb > 2:
                st.error(f"❌ File too large: {file_size_mb:.2f} MB (max 2 MB)")
            else:
                st.info(f"📄 {uploaded_file.name} ({file_size_mb:.2f} MB)")

                if st.button("💾 Upload", key=f"upload_runbook_btn_{st.session_state.upload_counter}"):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        resp = requests.post(f"{API_URL}/api/runbooks/upload", files=files, timeout=10)
                        resp.raise_for_status()
                        result = resp.json()
                        st.success(f"✅ {result['message']}")
                        st.info("⏳ Indexing in background... (10-15 seconds)")
                        # Increment counter to reset file uploader
                        st.session_state.upload_counter += 1
                        st.rerun()
                    except requests.exceptions.HTTPError as e:
                        try:
                            error_detail = e.response.json().get('detail', str(e))
                        except:
                            error_detail = str(e)
                        st.error(f"❌ Upload failed: {error_detail}")
                    except Exception as e:
                        st.error(f"❌ Upload failed: {e}")

        st.divider()

        # List existing runbooks
        try:
            runbooks_resp = requests.get(f"{API_URL}/api/runbooks", timeout=5)
            if runbooks_resp.status_code == 200:
                runbooks = runbooks_resp.json().get("runbooks", [])

                if runbooks:
                    sample_count = sum(1 for r in runbooks if r.get('source') == 'sample')
                    upload_count = sum(1 for r in runbooks if r.get('source') == 'uploaded')
                    st.caption(f"**{len(runbooks)} runbook(s)** ({sample_count} sample, {upload_count} uploaded)")

                    for rb in runbooks:
                        size_kb = rb['size'] / 1024
                        source_icon = "📘" if rb.get('source') == 'sample' else "📗"
                        is_deletable = rb.get('deletable', False)

                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.text(f"{source_icon} {rb['filename']} ({size_kb:.1f} KB)")
                        with col2:
                            if is_deletable:
                                if st.button("🗑️", key=f"del_rb_{rb['filename']}", help="Delete uploaded runbook"):
                                    try:
                                        del_resp = requests.delete(
                                            f"{API_URL}/api/runbooks/{rb['filename']}",
                                            timeout=5
                                        )
                                        del_resp.raise_for_status()
                                        st.success(f"✅ Deleted: {rb['filename']}")
                                        # Increment counter to reset file uploader
                                        st.session_state.upload_counter += 1
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Delete failed: {e}")
                            else:
                                st.text("🔒")
                else:
                    st.caption("No runbooks found")
        except Exception:
            st.caption("Cannot load runbooks")

    # Prompt Manager Section
    st.divider()
    with st.expander("⚙️ Prompt Manager", expanded=False):
        st.caption("Manage AI prompts & select active mode")

        # Get list of prompts
        try:
            prompts_resp = requests.get(f"{API_URL}/api/prompts", timeout=5)
            if prompts_resp.status_code == 200:
                prompts = prompts_resp.json()

                # Get current active prompt
                config_resp = requests.get(f"{API_URL}/api/config/active-prompt", timeout=5)
                active_config = config_resp.json() if config_resp.status_code == 200 else {}
                current_active = active_config.get("active_prompt")

                # Prompt selector with auto-apply on change
                st.caption("**Active Prompt Mode:**")
                prompt_options = ["Auto (Strategy-based)"] + [p["name"] for p in prompts]
                current_index = 0
                if current_active:
                    try:
                        current_index = prompt_options.index(current_active)
                    except ValueError:
                        current_index = 0

                selected_prompt = st.selectbox(
                    "Active Prompt",
                    prompt_options,
                    index=current_index,
                    key="prompt_selector",
                    label_visibility="collapsed",
                    help="Select which prompt template to use for all answers"
                )

                # Auto-apply when selection changes
                if selected_prompt != (current_active or "Auto (Strategy-based)"):
                    try:
                        new_active = None if selected_prompt == "Auto (Strategy-based)" else selected_prompt
                        set_resp = requests.post(
                            f"{API_URL}/api/config/active-prompt",
                            json={"active_prompt": new_active},
                            timeout=5
                        )
                        set_resp.raise_for_status()
                        st.success(f"✅ Now using: **{selected_prompt}**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed to change: {e}")

                # Show current active mode
                current_display = current_active or "Auto (Strategy-based)"
                st.caption(f"🟢 Currently active: **{current_display}**")

                st.divider()

                # Create new prompt button
                if not st.session_state.show_prompt_editor:
                    if st.button("+ New Custom Prompt", key="new_prompt_btn", use_container_width=True):
                        st.session_state.show_prompt_editor = True
                        st.session_state.edit_prompt_id = None
                        st.rerun()

                # Prompt editor (create/edit)
                if st.session_state.show_prompt_editor:
                    with st.form(key="create_prompt_form"):
                        st.caption("**Create Custom Prompt:**")

                        prompt_name = st.text_input(
                            "Name*",
                            key="new_prompt_name",
                            placeholder="e.g., Concise Mode"
                        )

                        prompt_desc = st.text_input(
                            "Description",
                            key="new_prompt_desc",
                            placeholder="Brief description (optional)"
                        )

                        prompt_text = st.text_area(
                            "Template* (use {assistant_name} and {context})",
                            value="You are {assistant_name}.\n\n{context}\n\nAnswer:",
                            key="new_prompt_text",
                            height=150
                        )

                        col_save, col_cancel = st.columns(2)
                        with col_save:
                            submit = st.form_submit_button("💾 Save", use_container_width=True)
                        with col_cancel:
                            cancel = st.form_submit_button("Cancel", use_container_width=True)

                        if cancel:
                            st.session_state.show_prompt_editor = False
                            st.rerun()

                        if submit:
                            if not prompt_name or not prompt_text:
                                st.error("❌ Name and template are required")
                            else:
                                try:
                                    create_resp = requests.post(
                                        f"{API_URL}/api/prompts",
                                        json={
                                            "name": prompt_name,
                                            "description": prompt_desc if prompt_desc else None,
                                            "prompt_text": prompt_text
                                        },
                                        timeout=5
                                    )
                                    create_resp.raise_for_status()
                                    st.success(f"✅ Created: {prompt_name}")
                                    st.session_state.show_prompt_editor = False
                                    st.rerun()
                                except requests.exceptions.HTTPError as e:
                                    try:
                                        error_detail = e.response.json().get('detail', str(e))
                                    except:
                                        error_detail = str(e)
                                    st.error(f"❌ {error_detail}")
                                except Exception as e:
                                    st.error(f"❌ Failed: {e}")

                    st.divider()

                # List existing prompts
                builtin_prompts = [p for p in prompts if p.get("is_builtin")]
                custom_prompts = [p for p in prompts if not p.get("is_builtin")]

                if builtin_prompts:
                    st.caption(f"**🔒 Built-in** ({len(builtin_prompts)})")
                    for prompt in builtin_prompts:
                        st.text(f"📌 {prompt['name']}")
                        if st.session_state.get(f"show_builtin_{prompt['prompt_id']}", False):
                            st.caption(f"*{prompt.get('description', 'No description')}*")
                            st.code(prompt['prompt_text'][:300] + "..." if len(prompt['prompt_text']) > 300 else prompt['prompt_text'])
                            if st.button("▲ Hide", key=f"hide_builtin_{prompt['prompt_id']}", use_container_width=True):
                                st.session_state[f"show_builtin_{prompt['prompt_id']}"] = False
                                st.rerun()
                        else:
                            if st.button("▼ View", key=f"view_builtin_{prompt['prompt_id']}", use_container_width=True):
                                st.session_state[f"show_builtin_{prompt['prompt_id']}"] = True
                                st.rerun()

                if custom_prompts:
                    st.caption(f"**✏️ Custom** ({len(custom_prompts)})")
                    for prompt in custom_prompts:
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.text(f"📝 {prompt['name']}")
                        with col2:
                            if st.button("🗑️", key=f"del_prompt_{prompt['prompt_id']}", help="Delete", use_container_width=True):
                                try:
                                    del_resp = requests.delete(
                                        f"{API_URL}/api/prompts/{prompt['prompt_id']}",
                                        timeout=5
                                    )
                                    del_resp.raise_for_status()
                                    st.success(f"✅ Deleted: {prompt['name']}")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Failed: {e}")

                        if st.session_state.get(f"show_custom_{prompt['prompt_id']}", False):
                            st.caption(f"*{prompt.get('description', 'No description')}*")
                            st.code(prompt['prompt_text'][:300] + "..." if len(prompt['prompt_text']) > 300 else prompt['prompt_text'])
                            if st.button("▲ Hide", key=f"hide_custom_{prompt['prompt_id']}", use_container_width=True):
                                st.session_state[f"show_custom_{prompt['prompt_id']}"] = False
                                st.rerun()
                        else:
                            if st.button("▼ View", key=f"view_custom_{prompt['prompt_id']}", use_container_width=True):
                                st.session_state[f"show_custom_{prompt['prompt_id']}"] = True
                                st.rerun()

        except Exception as e:
            st.caption(f"Cannot load prompts: {e}")

    # Discussions Section
    st.divider()
    st.subheader("Discussions")

    col_new, col_del_all = st.columns([3, 2])
    with col_new:
        if st.button("+ New Discussion", use_container_width=True):
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.rerun()

    with col_del_all:
        if st.button("🗑️ Clear All", use_container_width=True, type="secondary"):
            st.session_state.confirm_delete_all = True
            st.rerun()

    st.divider()
    st.caption("Saved Sessions (PostgreSQL)")

    # Show delete ALL confirmation dialog
    if st.session_state.confirm_delete_all:
        try:
            sessions = requests.get(f"{API_URL}/api/sessions", timeout=5).json()
            session_count = len(sessions)

            st.error(f"⚠️ **Delete ALL {session_count} session(s)?**\n\nThis action cannot be undone!")

            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("🗑️ Delete All", key="confirm_delete_all_yes", type="primary", use_container_width=True):
                    try:
                        resp = requests.delete(f"{API_URL}/api/sessions", timeout=5)
                        resp.raise_for_status()
                        result = resp.json()
                        # Start a new session
                        st.session_state.session_id = str(uuid.uuid4())
                        st.session_state.messages = []
                        st.session_state.confirm_delete_all = False
                        st.success(f"✅ {result['message']}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed: {e}")
                        st.session_state.confirm_delete_all = False

            with col_cancel:
                if st.button("Cancel", key="confirm_delete_all_no", use_container_width=True):
                    st.session_state.confirm_delete_all = False
                    st.rerun()

            st.divider()
        except Exception:
            st.session_state.confirm_delete_all = False

    # Show delete confirmation dialog at the top if needed
    if st.session_state.confirm_delete:
        try:
            sessions_temp = requests.get(f"{API_URL}/api/sessions", timeout=5).json()
            session_to_delete = st.session_state.confirm_delete
            session_title = next((s['title'] for s in sessions_temp if s['session_id'] == session_to_delete), "Unknown")

            st.warning(f"⚠️ **Delete this session?**\n\n`{session_title[:50]}`")

            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("🗑️ Delete", key="confirm_delete_yes", type="primary", use_container_width=True):
                    try:
                        resp = requests.delete(
                            f"{API_URL}/api/sessions/{session_to_delete}", timeout=5
                        )
                        resp.raise_for_status()
                        # If we deleted the current session, start a new one
                        if st.session_state.session_id == session_to_delete:
                            st.session_state.session_id = str(uuid.uuid4())
                            st.session_state.messages = []
                        st.session_state.confirm_delete = None
                        st.success("✅ Deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Failed: {e}")
                        st.session_state.confirm_delete = None

            with col_cancel:
                if st.button("Cancel", key="confirm_delete_no", use_container_width=True):
                    st.session_state.confirm_delete = None
                    st.rerun()

            st.divider()
        except Exception:
            st.session_state.confirm_delete = None

    # List sessions
    try:
        sessions = requests.get(f"{API_URL}/api/sessions", timeout=5).json()
        for s in sessions:
            label = f"{s['title'][:45]}..." if len(s['title']) > 45 else s['title']
            session_id_short = s['session_id'][:8]

            col_btn, col_del = st.columns([5, 1])

            with col_btn:
                # Session button
                if st.button(
                    f"💬 {label}",
                    key=f"session_{s['session_id']}",
                    use_container_width=True,
                    help=f"ID: {session_id_short}"
                ):
                    st.session_state.session_id = s["session_id"]
                    hist = requests.get(
                        f"{API_URL}/api/sessions/{s['session_id']}", timeout=5
                    ).json()
                    st.session_state.messages = hist
                    st.rerun()

            with col_del:
                # Delete button
                if st.button(
                    "🗑️",
                    key=f"delete_{s['session_id']}",
                    help="Delete this session",
                    use_container_width=True
                ):
                    st.session_state.confirm_delete = s["session_id"]
                    st.rerun()

    except Exception:
        st.caption("Waiting for API...")

# Chat messages
for msg_idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Extract source citations and add view buttons
        if msg["role"] == "assistant" and "📚 **Source:**" in msg["content"]:
            import re
            sources = re.findall(r'📚 \*\*Source:\*\* ([^\n]+)', msg["content"])
            if sources:
                filenames = [f.strip() for f in sources[0].split(',')]
                st.caption("View runbooks:")
                cols = st.columns(len(filenames))
                for idx, filename in enumerate(filenames):
                    with cols[idx]:
                        if st.button(f"📄 {filename}", key=f"view_msg{msg_idx}_{idx}_{filename}"):
                            st.session_state.view_runbook = filename
                            st.rerun()

        if msg.get("model"):
            st.caption(f"Served by: `{msg['model']}`")

    # Show runbook viewer INLINE right after this message if it's the one being viewed
    if msg["role"] == "assistant" and "📚 **Source:**" in msg["content"] and st.session_state.view_runbook:
        import re
        sources = re.findall(r'📚 \*\*Source:\*\* ([^\n]+)', msg["content"])
        if sources:
            filenames = [f.strip() for f in sources[0].split(',')]
            # Check if the current runbook is from this message's sources
            if st.session_state.view_runbook in filenames:
                # Show the runbook content right here
                with st.expander(f"📖 {st.session_state.view_runbook}", expanded=True):
                    try:
                        resp = requests.get(
                            f"{API_URL}/api/runbooks/{st.session_state.view_runbook}/content",
                            timeout=5
                        )
                        resp.raise_for_status()
                        data = resp.json()

                        # Scrollable container for runbook content
                        with st.container(height=500, border=True):
                            st.markdown(data["content"])

                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.caption(f"📌 Source: {data['source']} | Size: {data['size']} bytes")
                        with col2:
                            if st.button("✕ Close", key=f"close_runbook_msg{msg_idx}", use_container_width=True):
                                st.session_state.view_runbook = None
                                st.rerun()

                    except Exception as e:
                        st.error(f"Failed to load runbook: {e}")

if prompt := st.chat_input("Ask an OpenShift question..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            resp = requests.post(
                f"{API_URL}/api/chat",
                json={"session_id": st.session_state.session_id, "message": prompt},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            st.markdown(data["reply"])
            st.caption(f"Served by: `{data['model_used']}`")
            st.session_state.messages.append(
                {"role": "assistant", "content": data["reply"], "model": data["model_used"]}
            )
            # Rerun to show source buttons
            st.rerun()
