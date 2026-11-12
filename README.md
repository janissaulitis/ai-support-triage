# AI support inbox triage

Demo for a fictional consumer lender. Customer emails in Latvian, Lithuanian, Polish, Spanish, Romanian and English are read by an AI model (Google Gemini), which returns topic, urgency, a one-line summary and a draft reply in the customer's language. Fixed business rules then route each email to a team and force a person to review fraud, hardship, complaints, data requests and anything the model is unsure about.

- `triage.py` – prompt, response schema, business rules, scoring
- `data/test_emails.json` – 96 invented, labelled emails (16 per language, 2 per topic), built by `data/build_testset.py`
- `app.py` – Streamlit app: inbox, try your own email, accuracy test

Set `GEMINI_API_KEY` in Streamlit secrets. Without it the app falls back to simple keyword rules.
