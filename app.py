"""AI support inbox for a fictional consumer lender. Run: streamlit run app.py"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import importlib

import triage as T

T = importlib.reload(T)  # Streamlit Cloud keeps old copies of imported files after an update; always use the latest

st.set_page_config(page_title="AI support inbox triage", page_icon="📨", layout="wide")
st.markdown("<style>.block-container{max-width:1240px;padding-top:2.2rem}</style>", unsafe_allow_html=True)

HERE = Path(__file__).parent
TEST = json.loads((HERE / "data" / "test_emails.json").read_text(encoding="utf-8"))


def secret(name, default=""):
    try:
        return st.secrets.get(name) or os.environ.get(name, default)
    except Exception:
        return os.environ.get(name, default)


API_KEY = secret("GEMINI_API_KEY")
MODEL_SETTING = secret("GEMINI_MODEL", "")
FLAG = {"lv": "🇱🇻", "lt": "🇱🇹", "pl": "🇵🇱", "es": "🇪🇸", "ro": "🇷🇴", "en": "🇬🇧", "ru": "🇷🇺", "de": "🇩🇪", "other": "🌐"}
URG = {"high": "🔴 high", "medium": "🟠 medium", "low": "⚪ low"}

# the inbox shown on the first screen: 9 emails, every language, the topics that matter most
INBOX_IDS = ["E015", "E020", "E043", "E062", "E073", "E086", "E009", "E077", "E055"]
INBOX = [t for i in INBOX_IDS for t in TEST if t["id"] == i]


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def model_names():
    return T.pick_models(API_KEY, MODEL_SETTING)


@st.cache_data(show_spinner=False, max_entries=200, ttl=60 * 60 * 24 * 7)
def run_ai(emails_json: str, models: list, version: str):
    """Cached for everyone: the same emails are only sent to the AI once a week."""
    emails = json.loads(emails_json)
    note = st.empty()
    results, used = T.triage_ai(
        emails, API_KEY, models,
        on_progress=lambda done, n: note.caption(f"{done} of {n} emails read…"),
        on_wait=lambda why, k, w: note.caption(f"Waiting {w:.0f} s ({why}), attempt {k} of 6…"))
    note.empty()
    return [r.__dict__ for r in results], used


def ai_error_text(e):
    msg = str(e)
    if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
        return "The free AI tier is busy (too many requests this minute). Wait a minute and click again."
    return f"The AI service did not answer: {msg[:400]}"


def triage(emails):
    payload = json.dumps([{"id": e["id"], "text": e["text"]} for e in emails], ensure_ascii=False)
    if not API_KEY:
        return [T.Result(**r.__dict__) for r in T.triage_rules(json.loads(payload))], "keyword rules (no AI key set)"
    try:
        model = model_names()
    except T.AIError:
        raise
    except Exception as e:
        raise T.AIError(str(e)) from e
    rows, used = run_ai(payload, model, T.PROMPT_VERSION)
    return [T.Result(**r) for r in rows], used


def result_table(emails, results):
    df = pd.DataFrame([{
        "": FLAG.get(r.language, "🌐"),
        "Urgency": URG[r.urgency],
        "Topic": r.topic.replace("_", " "),
        "Team": r.team,
        "Person must review": "👤 yes" if r.needs_human else "✓ quick check",
        "Summary": r.summary_en,
    } for r in results])
    order = {"🔴 high": 0, "🟠 medium": 1, "⚪ low": 2}
    df["_o"] = df["Urgency"].map(order)
    st.dataframe(df.sort_values("_o").drop(columns="_o"), hide_index=True, width="stretch",
                 column_config={"": st.column_config.TextColumn(width="small"), "Summary": st.column_config.TextColumn(width="large")})


def result_cards(emails, results):
    text = {e["id"]: e["text"] for e in emails}
    for r in sorted(results, key=lambda r: ["high", "medium", "low"].index(r.urgency)):
        with st.expander(f"{FLAG.get(r.language, '🌐')}  {URG[r.urgency]} · {r.topic.replace('_', ' ')} → {r.team}  —  {r.summary_en}"):
            a, b = st.columns(2)
            a.markdown("**Customer wrote**")
            a.info(text[r.id])
            if r.flags:
                a.markdown("**Flags:** " + " ".join(f"`{f}`" for f in r.flags))
            a.caption(f"{'👤 A person reviews before sending: ' if r.needs_human else '✓ '}{r.why_human}. "
                      f"AI confidence {r.confidence:.0%}.")
            b.markdown(f"**Draft reply ({T.LANGS.get(r.language, r.language)})**")
            b.success(r.reply)


def _model_label():
    try:
        return ", then ".join(model_names()[:2])
    except Exception as e:
        return f"model lookup failed: {str(e)[:120]}"


# ---------------------------------------------------------------- header
st.title("AI support inbox for a lender")
st.markdown("**Reads customer emails in 6 languages, sorts them by topic and urgency, routes them to the right team "
            "and drafts a reply in the customer's language.** A person always reviews the sensitive ones.")
with st.container(horizontal=True):
    with st.popover("How it works"):
        st.markdown(
            "1. Click **Sort the inbox**: 9 emails in Latvian, Lithuanian, Polish, Spanish, Romanian and English.\n"
            "2. The AI reads each one and returns the topic, urgency, a summary and a draft reply.\n"
            "3. Fixed business rules then decide the team, and force a person to review `fraud`, `hardship`, "
            "`complaints` and `data requests`, or anything the AI is unsure about.\n"
            "4. **Try your own email** in any language, or run the **96-email accuracy test**."
        )
st.caption("Demo for a fictional lender. All emails are invented. Runs on Google Gemini"
           + (f" ({_model_label()})" if API_KEY else "")
           + ("" if API_KEY else " — **no AI key set, so this copy runs on simple keyword rules**") + ".")

tab_inbox, tab_own, tab_test = st.tabs(["📥 Inbox", "✍️ Try your own email", "🎯 Accuracy test (96 emails)"])

# ---------------------------------------------------------------- inbox
with tab_inbox:
    st.markdown("**This morning's inbox**")
    st.dataframe(pd.DataFrame([{"": FLAG[e["lang"]], "Email": e["text"]} for e in INBOX]), hide_index=True, width="stretch",
                 column_config={"": st.column_config.TextColumn(width="small")})
    if st.button("▶  Sort the inbox", type="primary"):
        st.session_state.inbox_go = True
    if st.session_state.get("inbox_go"):
        try:
            with st.spinner("The AI is reading 9 emails…"):
                res, used = triage(INBOX)
        except T.AIError as e:
            st.error(ai_error_text(e))
            st.stop()
        teams = pd.Series([r.team for r in res]).value_counts()
        cols = st.columns(len(teams) + 1)
        cols[0].metric("Need a person", sum(r.needs_human for r in res), help="Always reviewed: fraud, hardship, complaints, data requests, or AI unsure")
        for c, (team, n) in zip(cols[1:], teams.items()):
            c.metric(team, n)
        result_table(INBOX, res)
        st.markdown("**Open an email to see the draft reply**")
        result_cards(INBOX, res)
        st.caption(f"Model: {used}")

# ---------------------------------------------------------------- your own
with tab_own:
    st.markdown("Write or paste a customer email in **any language**. Try something tricky: two problems in one email, "
                "sarcasm, no diacritics, or a scam the customer fell for.")
    own = st.text_area("Customer email", height=140, placeholder="e.g. Sveiki, man vakar nozaga maku ar ID karti. Vai kāds var paņemt aizdevumu uz mana vārda?")
    if st.button("▶  Sort this email", type="primary", disabled=not own.strip()):
        try:
            with st.spinner("Reading…"):
                res, used = triage([{"id": "YOU", "text": own.strip()[:3000]}])
            result_cards([{"id": "YOU", "text": own.strip()}], res)
            st.caption(f"Model: {used}")
        except T.AIError as e:
            st.error(ai_error_text(e))

# ---------------------------------------------------------------- accuracy test
with tab_test:
    st.markdown("**96 invented emails, each with the answer a careful support lead would give.** 16 per language, "
                "2 per topic, including tricky ones: two problems in one email, sarcasm, missing diacritics, "
                "a customer who paid a scammer's account. The test checks what matters to the business:")
    st.markdown("- **Team**: did it reach the right people?  \n- **Topic** and **urgency**  \n"
                "- **Missed risk**: a fraud, hardship or regulator threat that slipped through without a person seeing it. This must be **0**.")
    with st.expander("See all 96 emails and their expected answers"):
        st.dataframe(pd.DataFrame(TEST)[["id", "lang", "text", "topic", "urgency", "team", "note"]], hide_index=True, width="stretch")
    if st.button("▶  Run the test", type="primary"):
        st.session_state.test_go = True
    if st.session_state.get("test_go"):
        try:
            with st.spinner("Sending 96 emails in batches of 8 (about a minute on the free tier)…"):
                res, used = triage(TEST)
        except T.AIError as e:
            st.error(ai_error_text(e))
            st.stop()
        s = T.score(TEST, res)
        c = st.columns(4)
        c[0].metric("Right team", f"{s['team']:.0%}")
        c[1].metric("Right topic", f"{s['topic']:.0%}")
        c[2].metric("Right urgency", f"{s['urgency']:.0%}")
        c[3].metric("Missed risk", s["missed_risk"], help="High-risk emails that no person would have seen. Target: 0.")
        st.markdown("**Right team, by language**")
        st.bar_chart(pd.Series({f"{FLAG[k]} {T.LANGS[k]}": v * 100 for k, v in s["by_lang"].items()}, name="% right"), horizontal=True, height=240, color="#2fb985")
        misses = [r for r in s["rows"] if not (r["topic_ok"] and r["urgency_ok"])]
        st.markdown(f"**Where it disagreed with the expected answer ({len(misses)})**")
        if misses:
            st.table(pd.DataFrame(misses)[["id", "lang", "text", "expected", "got", "note"]].set_index("id"))
        st.caption(f"Model: {used} · prompt {T.PROMPT_VERSION} · results are cached for a week, so repeat runs are instant.")

st.divider()
st.caption("Built with Claude Code by Jānis Saulītis · engine: `triage.py` · the team, the review rules and the escalation "
           "words are fixed code, not left to the AI.")
