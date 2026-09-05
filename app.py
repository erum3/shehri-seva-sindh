import os
import re
import json
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from groq import Groq
from pypdf import PdfReader
from docx import Document

DB_PATH = "complaints.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

DEPARTMENTS = [
    "Sanitation",
    "Water Supply",
    "Sewerage/Drainage",
    "Roads & Street Repair",
    "Street Lights",
    "Parks & Horticulture",
    "Encroachment",
    "Building/Planning",
    "Municipal Services",
    "Other",
]

STATUSES = ["Submitted", "Routed", "Under Review", "In Progress", "Resolved", "Rejected"]

st.set_page_config(
    page_title="Shehri Seva Sindh",
    page_icon="🏛️",
    layout="wide",
)

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            citizen_name TEXT,
            phone TEXT,
            area TEXT,
            complaint_text TEXT,
            attachment_name TEXT,
            category TEXT,
            department TEXT,
            priority TEXT,
            ai_summary TEXT,
            ai_action TEXT,
            status TEXT DEFAULT 'Submitted',
            officer_note TEXT DEFAULT '',
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def make_tracking_id():
    return "HMC-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[-10:]

def extract_pdf(file_bytes):
    import io
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)

def extract_docx(file_bytes):
    import io
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs)

def extract_image_ocr(file_bytes):
    try:
        import io
        from PIL import Image
        import pytesseract
        image = Image.open(io.BytesIO(file_bytes))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"[Image OCR unavailable: {e}]"

def extract_attachment(uploaded_file):
    if uploaded_file is None:
        return ""
    data = uploaded_file.getvalue()
    suffix = Path(uploaded_file.name).suffix.lower()

    if suffix == ".pdf":
        return extract_pdf(data)
    if suffix == ".docx":
        return extract_docx(data)
    if suffix in [".png", ".jpg", ".jpeg", ".webp"]:
        return extract_image_ocr(data)
    if suffix == ".txt":
        return data.decode("utf-8", errors="ignore")
    return ""

def get_groq_client():
    api_key = None
    try:
        api_key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        pass
    api_key = api_key or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return Groq(api_key=api_key)

def analyze_with_ai(complaint):
    client = get_groq_client()
    if client is None:
        return {
            "category": "Other",
            "department": "Other",
            "priority": "Medium",
            "summary": complaint[:500],
            "recommended_action": "Forward to the appropriate municipal officer for manual review."
        }

    system_prompt = f"""
You are the AI triage assistant for a Sindh municipal citizen complaint portal.

Your job is ONLY to:
1. Understand the citizen complaint.
2. Classify it into exactly one category/department from this list:
{DEPARTMENTS}
3. Assign priority: Low, Medium, High, or Emergency.
4. Write a concise factual summary.
5. Recommend the next administrative action.

Important:
- Do NOT claim that a complaint is resolved.
- Do NOT invent facts, laws, deadlines, officer names, or fees.
- If information is missing, say that it needs human verification.
- The final decision and resolution status belong to municipal officers.
- Return ONLY valid JSON with these keys:
category, department, priority, summary, recommended_action
"""

    user_prompt = f"Citizen complaint:\n{complaint[:12000]}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=700,
        )
        content = response.choices[0].message.content.strip()
        content = re.sub(r"^```json\s*|\s*```$", "", content)
        result = json.loads(content)

        if result.get("department") not in DEPARTMENTS:
            result["department"] = "Other"
        if result.get("priority") not in ["Low", "Medium", "High", "Emergency"]:
            result["priority"] = "Medium"
        return result
    except Exception as e:
        return {
            "category": "Other",
            "department": "Other",
            "priority": "Medium",
            "summary": complaint[:500],
            "recommended_action": f"AI analysis failed; human review required. Technical detail: {e}"
        }

def insert_complaint(data):
    conn = get_conn()
    conn.execute("""
        INSERT INTO complaints
        (tracking_id, citizen_name, phone, area, complaint_text, attachment_name,
         category, department, priority, ai_summary, ai_action, status,
         officer_note, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)
    conn.commit()
    conn.close()

def load_complaints():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM complaints ORDER BY id DESC", conn
    )
    conn.close()
    return df

def update_complaint(tracking_id, status, note):
    conn = get_conn()
    conn.execute(
        "UPDATE complaints SET status=?, officer_note=?, updated_at=? WHERE tracking_id=?",
        (status, note, datetime.now().isoformat(timespec="seconds"), tracking_id)
    )
    conn.commit()
    conn.close()

def save_attachment(tracking_id, uploaded_file):
    if uploaded_file is None:
        return
    suffix = Path(uploaded_file.name).suffix
    target = UPLOAD_DIR / f"{tracking_id}{suffix}"
    target.write_bytes(uploaded_file.getvalue())

init_db()

st.title("🏛️ Shehri Seva Sindh")
st.caption("AI-assisted Municipal Citizen Complaint Portal — prototype")

with st.sidebar:
    st.header("Portal")
    mode = st.radio("Select mode", ["Citizen Portal", "Officer Dashboard"])
    st.divider()
    st.info(
        "AI assists with classification and routing. "
        "Municipal officers remain responsible for approval and resolution."
    )

if mode == "Citizen Portal":
    st.header("Register a Municipal Complaint")
    st.write("Submit a complaint as text or attach a PDF, DOCX, TXT, or image.")

    with st.form("complaint_form"):
        name = st.text_input("Citizen name")
        phone = st.text_input("Phone / contact")
        area = st.text_input("Area / locality")
        complaint = st.text_area(
            "Describe your complaint",
            height=160,
            placeholder="Example: Street light has not been working for 10 days near..."
        )
        attachment = st.file_uploader(
            "Optional evidence/document",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"]
        )
        submitted = st.form_submit_button("🚀 Submit Complaint")

    if submitted:
        attachment_text = extract_attachment(attachment)
        combined_text = "\n\n".join(x for x in [complaint, attachment_text] if x.strip()).strip()

        if not combined_text:
            st.error("Please enter complaint text or upload a readable document/image.")
        else:
            with st.spinner("AI is understanding and routing your complaint..."):
                result = analyze_with_ai(combined_text)

            tracking_id = make_tracking_id()
            attachment_name = attachment.name if attachment else ""

            insert_complaint((
                tracking_id,
                name,
                phone,
                area,
                combined_text,
                attachment_name,
                result.get("category", "Other"),
                result.get("department", "Other"),
                result.get("priority", "Medium"),
                result.get("summary", ""),
                result.get("recommended_action", ""),
                "Routed",
                "",
                datetime.now().isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
            ))
            save_attachment(tracking_id, attachment)

            st.success(f"Complaint registered successfully. Tracking ID: {tracking_id}")
            st.info(
                f"AI route: **{result.get('department')}** | "
                f"Priority: **{result.get('priority')}**"
            )

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("AI Summary")
                st.write(result.get("summary", ""))
            with c2:
                st.subheader("Recommended Action")
                st.write(result.get("recommended_action", ""))

    st.divider()
    st.subheader("Track a Complaint")
    tracking = st.text_input("Enter tracking ID", placeholder="HMC-...")
    if tracking:
        conn = get_conn()
        row = conn.execute(
            "SELECT * FROM complaints WHERE tracking_id=?",
            (tracking.strip(),)
        ).fetchone()
        conn.close()

        if row:
            st.success(f"Status: {row['status']}")
            st.write(f"**Department:** {row['department']}")
            st.write(f"**Priority:** {row['priority']}")
            st.write(f"**Submitted:** {row['created_at']}")
            if row["officer_note"]:
                st.write(f"**Officer update:** {row['officer_note']}")
        else:
            st.warning("Tracking ID not found.")

else:
    st.header("Municipal Officer Dashboard")
    df = load_complaints()

    if df.empty:
        st.info("No complaints have been registered yet.")
    else:
        total = len(df)
        resolved = int((df["status"] == "Resolved").sum())
        active = total - resolved
        high = int(df["priority"].isin(["High", "Emergency"]).sum())

        a, b, c, d = st.columns(4)
        a.metric("Total", total)
        b.metric("Resolved", resolved)
        c.metric("Active", active)
        d.metric("High/Emergency", high)

        st.divider()

        f1, f2 = st.columns(2)
        with f1:
            status_filter = st.multiselect(
                "Filter by status",
                STATUSES,
                default=STATUSES
            )
        with f2:
            dept_filter = st.multiselect(
                "Filter by department",
                DEPARTMENTS,
                default=DEPARTMENTS
            )

        filtered = df[
            df["status"].isin(status_filter) &
            df["department"].isin(dept_filter)
        ]

        st.subheader("Complaint Dashboard")
        display_cols = [
            "tracking_id", "area", "category", "department",
            "priority", "status", "created_at"
        ]
        st.dataframe(filtered[display_cols], use_container_width=True, hide_index=True)

        st.subheader("Complaint Details / Officer Action")
        if not filtered.empty:
            selected = st.selectbox(
                "Select tracking ID",
                filtered["tracking_id"].tolist()
            )
            row = filtered[filtered["tracking_id"] == selected].iloc[0]

            left, right = st.columns(2)
            with left:
                st.write(f"**Citizen:** {row['citizen_name']}")
                st.write(f"**Area:** {row['area']}")
                st.write(f"**Department:** {row['department']}")
                st.write(f"**Priority:** {row['priority']}")
                st.write(f"**AI Summary:** {row['ai_summary']}")
            with right:
                st.write(f"**Complaint:** {row['complaint_text']}")
                st.write(f"**AI Recommended Action:** {row['ai_action']}")
                if row["attachment_name"]:
                    st.write(f"**Attachment:** {row['attachment_name']}")

            new_status = st.selectbox(
                "Officer decision / current status",
                STATUSES,
                index=STATUSES.index(row["status"]) if row["status"] in STATUSES else 0
            )
            officer_note = st.text_area(
                "Officer update / resolution note",
                value=row["officer_note"] or "",
                placeholder="Enter verified action taken or reason for rejection."
            )

            if st.button("💾 Update Complaint"):
                update_complaint(selected, new_status, officer_note)
                st.success("Complaint updated.")
                st.rerun()

        st.divider()
        st.subheader("Department Workload")
        workload = (
            df.groupby("department")
            .size()
            .reset_index(name="complaints")
            .sort_values("complaints", ascending=False)
        )
        st.bar_chart(workload.set_index("department"))

        st.download_button(
            "⬇️ Download Complaint Register CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name="municipal_complaints.csv",
            mime="text/csv",
        )
