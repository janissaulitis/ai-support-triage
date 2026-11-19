"""AI support inbox for a fictional consumer lender. Run: streamlit run app.py"""
import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

import importlib
import re

import kit
import triage as T

T = importlib.reload(T)  # Streamlit Cloud keeps old copies of imported files after an update; always use the latest
kit = importlib.reload(kit)

kit.page("Inbox Router", "Sorts customer emails in 6 languages and drafts the replies", mark="inbox", icon="📨",
         meta="For a lender's support team · runs on Google Gemini", theme="glass")

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
        daily = "PerDay" in msg or "per day" in msg.lower()
        detail = re.search(r"quotaId['\"]?:\s*['\"]([^'\"]+)", msg)
        what = f" ({detail.group(1)})" if detail else ""
        if daily:
            return f"Today's free AI requests are used up{what}. They reset every morning; until then, try again tomorrow."
        return f"The free AI tier is busy (too many requests this minute){what}. Wait a minute and click again."
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


# ---------------------------------------------------------------- saved runs
# A verified run is kept in data/verified/, so visitors see real results even when the free AI tier is used up.
SAVED = HERE / "data" / "verified"


def load_saved(name):
    try:
        d = json.loads((SAVED / f"{name}.json").read_text(encoding="utf-8"))
        return [T.Result(**r) for r in d["results"]], d
    except Exception:
        return None, None


def save_button(name, results, used):
    import datetime as _dt
    blob = json.dumps({"date": _dt.date.today().isoformat(), "model": used, "prompt": T.PROMPT_VERSION,
                       "results": [r.__dict__ for r in results]}, ensure_ascii=False, indent=1)
    st.download_button("Download this run (JSON)", blob, file_name=f"{name}.json", mime="application/json", key=f"dl_{name}")


def saved_label(meta):
    return f"Saved verified run from {meta['date']} · {meta['model']} · prompt {meta['prompt']}"


def show_error(e):
    st.error(ai_error_text(e))
    with st.expander("Technical detail"):
        st.code(str(e)[:900])


URG_TONE = {"high": "bad", "medium": "warn", "low": ""}


def result_table(emails, results):
    rows = sorted(results, key=lambda r: ["high", "medium", "low"].index(r.urgency))
    kit.table([{"l": r.language, "u": r.urgency.capitalize(), "t": r.topic.replace("_", " "), "team": r.team,
                "h": "Person first" if r.needs_human else "Quick check", "s": r.summary_en} for r in rows],
              [kit.col("", "l", "lang"), kit.col("Urgency", "u", "chip", {"High": "bad", "Medium": "warn"}),
               kit.col("Topic", "t", "chip", {}), kit.col("Team", "team", "strong"),
               kit.col("Review", "h", "chip", {"Person first": "warn", "Quick check": "good"}), kit.col("Summary", "s", "wrap")])


def detail_panel(text: str, r):
    urg = {"high": "bad", "medium": "warn", "low": ""}[r.urgency]
    head = (f"<span class='k-chip {urg}'>{html.escape(r.topic.replace('_', ' ').capitalize())} · {r.urgency}</span> "
            f"<span class='k-chip'>→ {html.escape(r.team)}</span> <span class='k-chip'>{html.escape(T.LANGS.get(r.language, r.language))}</span>")
    if r.needs_human:
        foot = (f"<b>No AI reply.</b> {html.escape(r.why_human[:1].upper() + r.why_human[1:])}. Fraud, hardship, complaints and data "
                "requests always go to a person.")
    else:
        foot = f"<b>Draft reply, ready after a quick check</b><div class='k-mail reply' style='margin-top:8px'>{html.escape(r.reply)}</div>"
    st.markdown(f"<div class='k-detail-p'>{head}<blockquote>“{html.escape(text)}”</blockquote>"
                f"<div class='en'>In English: {html.escape(r.summary_en)}</div><div class='rule'>{foot}</div>"
                f"<div class='en' style='margin-top:10px;font-size:12.5px'>AI confidence {r.confidence:.0%}</div></div>",
                unsafe_allow_html=True)


def inbox_view(emails, results):
    text = {e["id"]: e["text"] for e in emails}
    rows = sorted(results, key=lambda r: (["high", "medium", "low"].index(r.urgency), not r.needs_human))
    labels = [f"{r.language.upper()} · {r.summary_en}" for r in rows]
    left, right = st.columns([3, 2], gap="medium")
    with right:
        pick = st.selectbox("Open an email", range(len(rows)), format_func=lambda i: labels[i], key="open_mail")
        detail_panel(text[rows[pick].id], rows[pick])
    with left:
        st.markdown("<div class='k-ib'>" + "".join(
            f"<div class='k-ib-r{' sel' if i == pick else ''}'><span class='k-lang'>{r.language.upper()}</span>"
            f"<span class='t'>{html.escape(r.summary_en)}</span><span class='c'>{html.escape(r.topic.replace('_', ' ').capitalize())}</span>"
            f"<span class='k-st {'p' if r.needs_human else 'd'}'>{'PERSON ONLY' if r.needs_human else 'DRAFT READY'}</span></div>"
            for i, r in enumerate(rows)) + "</div>", unsafe_allow_html=True)


def result_cards(emails, results):
    text = {e["id"]: e["text"] for e in emails}
    for r in results:
        detail_panel(text[r.id], r)


def _model_label():
    try:
        return ", then ".join(model_names()[:2])
    except Exception as e:
        return f"model lookup failed: {str(e)[:120]}"


# ---------------------------------------------------------------- header
st.markdown("Reads each customer email, sorts it by **topic and urgency**, sends it to **the right team** and drafts a "
            "reply **in the customer's language**. Fraud, hardship, complaints and data requests always go to a person.")
with st.container(horizontal=True):
    with st.popover("How it works"):
        st.markdown(
            "1. Click **Sort the inbox**: 9 emails in Latvian, Lithuanian, Polish, Spanish, Romanian and English.\n"
            "2. The AI reads each one and returns the topic, urgency, a summary and a draft reply.\n"
            "3. Fixed business rules then decide the team, and force a person to review `fraud`, `hardship`, "
            "`complaints` and `data requests`, or anything the AI is unsure about.\n"
            "4. **Try your own email** in any language, or run the **96-email accuracy test**."
        )
st.caption("All emails are invented. " + (f"AI model: {_model_label()}." if API_KEY
                                            else "No AI key set, so this copy runs on simple keyword rules."))

tab_inbox, tab_own, tab_test = st.tabs(["Inbox", "Try your own email", "Accuracy test (96 emails)"])

# ---------------------------------------------------------------- inbox
with tab_inbox:
    st.markdown("**This morning's inbox**")
    kit.messages([{"lang": e["lang"], "text": e["text"], "sub": T.LANGS.get(e["lang"], e["lang"])} for e in INBOX])
    if st.button("▶  Sort the inbox", type="primary"):
        st.session_state.inbox_go = True
    if st.session_state.get("inbox_go"):
        live = True
        try:
            with st.spinner("The AI is reading 9 emails…"):
                res, used = triage(INBOX)
        except T.AIError as e:
            res, meta = load_saved("inbox")
            if res is None:
                show_error(e)
                st.stop()
            live = False
            st.warning(ai_error_text(e) + " Showing the last saved run instead.")
            used = saved_label(meta)
        teams = pd.Series([r.team for r in res]).value_counts()
        human = sum(r.needs_human for r in res)
        kit.answer("Inbox sorted", f"{len(res)} emails sorted, {human} go to a person first", "",
                   [("Sorted", f"{len(res)} / {len(INBOX)}"), ("To a person", str(human)), ("Drafts ready", str(len(res) - human)),
                    ("Languages", str(len({r.language for r in res})))])
        inbox_view(INBOX, res)
        st.caption(f"Model: {used}")
        if live and API_KEY:
            save_button("inbox", res, used)

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
            show_error(e)

# ---------------------------------------------------------------- accuracy test
with tab_test:
    st.markdown("**96 invented emails, each with the answer a careful support lead would give.** 16 per language, "
                "2 per topic, including tricky ones: two problems in one email, sarcasm, missing diacritics, "
                "a customer who paid a scammer's account. The test checks what matters to the business:")
    st.markdown("- **Team**: did it reach the right people?  \n- **Topic** and **urgency**  \n"
                "- **Missed risk**: a fraud, hardship or regulator threat that slipped through without a person seeing it. This must be **0**.")
    with st.expander("See all 96 emails and their expected answers"):
        kit.table([{**e, "topic": e["topic"].replace("_", " "), "urgency": e["urgency"].capitalize()} for e in TEST],
                  [kit.col("", "lang", "lang"), kit.col("Email", "text", "wrap"), kit.col("Topic", "topic", "chip", {}),
                   kit.col("Urgency", "urgency", "chip", {"High": "bad", "Medium": "warn"}), kit.col("Team", "team", "strong"),
                   kit.col("Why it's tricky", "note", "muted")], max_height=460)
    saved, meta = load_saved("test")
    if st.button("▶  Run it live" if saved else "▶  Run the test", type="primary"):
        st.session_state.test_go = True
    res = used = None
    if st.session_state.get("test_go"):
        try:
            with st.spinner("Sending 96 emails in batches of 12 (one to two minutes on the free tier)…"):
                res, used = triage(TEST)
            used = f"{used} · prompt {T.PROMPT_VERSION} · live run (cached for a week, so repeat runs are instant)"
        except T.AIError as e:
            show_error(e)
            if saved:
                st.info("Below: the last saved run.")
    if res is None and saved:
        res, used = saved, saved_label(meta)
    if res is not None:
        s = T.score(TEST, res)
        right = sum(r["topic_ok"] and r["urgency_ok"] for r in s["rows"])
        kit.answer("Accuracy test", f"{right} of {len(TEST)} emails sorted exactly right",
                   f"Missed risk: <b>{s['missed_risk']}</b>. No fraud, hardship or regulator threat slipped past a person."
                   if s["missed_risk"] == 0 else
                   f"Missed risk: <b>{s['missed_risk']}</b> high-risk emails would not have reached a person.",
                   [("Right team", f"{s['team']:.0%}"), ("Right topic", f"{s['topic']:.0%}"),
                    ("Right urgency", f"{s['urgency']:.0%}"), ("Missed risk", str(s["missed_risk"]))],
                   tone="good" if s["missed_risk"] == 0 else "bad")
        st.markdown("**Right team, by language**")
        kit.bars([{"label": T.LANGS[k], "value": v, "text": f"{v:.0%}"} for k, v in s["by_lang"].items()])
        misses = [r for r in s["rows"] if not (r["topic_ok"] and r["urgency_ok"])]
        st.markdown(f"**Where it disagreed with the expected answer ({len(misses)})**")
        if misses:
            kit.table(misses, [kit.col("", "lang", "lang"), kit.col("Email", "text", "wrap"),
                               kit.col("Expected", "expected", "chip", {}), kit.col("Got", "got", "chip", {}),
                               kit.col("Note", "note", "muted")])
        st.caption(used)
        if st.session_state.get("test_go") and API_KEY and "live run" in used:
            save_button("test", res, used.split(" · ")[0])

kit.footer("Google Gemini · triage.py")
