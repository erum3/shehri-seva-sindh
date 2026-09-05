# Shehri Seva Sindh — AI Municipal Citizen Complaint Portal

A beginner-friendly Streamlit prototype for registering, understanding, routing and tracking municipal citizen complaints.

## Main features

- Citizen complaint registration
- Text complaint input
- PDF, DOCX, TXT and image evidence upload
- PDF/DOCX text extraction
- OCR for images
- Groq-powered AI classification
- Automatic department routing
- Priority classification
- AI summary and recommended action
- Tracking ID for citizens
- Officer dashboard
- Complaint status workflow
- Officer notes
- Resolved/active statistics
- Department workload chart
- CSV export
- SQLite database

## Important governance rule

The AI does NOT decide that a complaint is legally resolved. It only assists with understanding, classification, routing and recommended action. A municipal officer changes the official status to Resolved after verification.

## Repository structure

```text
municipal-citizen-complaint-portal/
│
├── app.py
├── requirements.txt
├── packages.txt
├── README.md
├── .gitignore
└── .streamlit/
    └── config.toml
```

The SQLite database (`complaints.db`) and uploaded evidence folder are created automatically when the app runs.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Groq API key

Do NOT put the Groq API key inside `app.py` or GitHub.

For local testing, create:

```text
.streamlit/secrets.toml
```

with:

```toml
GROQ_API_KEY = "your_key_here"
```

For Streamlit Community Cloud, add the same secret in the app's Secrets settings.

## Deploy on Streamlit Community Cloud

1. Create a GitHub repository.
2. Upload:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`
   - `README.md`
   - `.streamlit/config.toml`
3. In Streamlit Community Cloud, create a new app.
4. Select the GitHub repository.
5. Select `app.py` as the main file.
6. Add `GROQ_API_KEY` in Streamlit Secrets.
7. Deploy.

## Cloudflare

For this prototype, Cloudflare is optional if you use Streamlit Community Cloud because Streamlit already provides a public deployment URL.

If you are running Streamlit locally or on your own server, Cloudflare Tunnel can expose the local application securely through a Cloudflare-managed tunnel. The exact Cloudflare setup depends on your domain/server arrangement.

## Prototype limitations

This is a hackathon/MVP prototype, not a production government system.

Before production, add:

- Officer authentication and role-based access
- Citizen authentication/OTP
- PostgreSQL or another production database
- Audit logs
- Encryption and secure document storage
- File size/type/security validation
- Malware scanning
- Department-specific permissions
- SLA and escalation rules
- Duplicate complaint detection
- GIS/location support
- Notifications by SMS/email/WhatsApp
- Formal approval workflow
- Backup and disaster recovery
- Urdu/Sindhi language support
- Privacy and government data-retention policies
