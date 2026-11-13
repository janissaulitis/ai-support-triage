"""Support inbox triage for a (fictional) consumer lender.

The AI model reads each customer email and returns: language, topic, urgency, a one-line English
summary, a draft reply in the customer's language, and flags. Code then applies fixed rules the
business would never leave to a model: which team owns each topic, when a human must review the
reply, and a few safety checks. A plain keyword classifier is included as a baseline, so the AI
is always measured against the simple alternative.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import dataclass, field

TOPICS = {
    "repayment": "How or when to pay, payment not showing, payment taken twice, change payment day.",
    "extension": "Wants to postpone a payment or extend the term, but is not describing financial hardship.",
    "early_repayment": "Wants to repay the whole loan early or asks what that costs.",
    "application_status": "Asks about a loan application: decision time, status, missing documents.",
    "hardship": "Cannot pay because of job loss, illness, income drop, divorce or similar; wants a solution.",
    "complaint": "Unhappy with service, fees, calls, staff or app and wants it addressed.",
    "data_request": "GDPR / personal data: access, copy, deletion, stop marketing, who data was shared with.",
    "fraud": "Loan or application they did not make, stolen ID or phone, phishing, fake calls, paid a fake account.",
}
TEAM = {
    "repayment": "Customer care", "early_repayment": "Customer care",
    "application_status": "Underwriting",
    "extension": "Collections", "hardship": "Collections",
    "complaint": "Complaints", "data_request": "Compliance", "fraud": "Fraud",
}
URGENCY = {
    "high": "Fraud; hardship; payment due today or tomorrow; threat to go to a regulator, lawyer, ombudsman or the media.",
    "medium": "Money not showing or taken twice; waiting several days; GDPR requests (legal deadline); ordinary complaints; extension not due yet.",
    "low": "General questions with no deadline or problem.",
}
LANGS = {"lv": "Latvian", "lt": "Lithuanian", "pl": "Polish", "es": "Spanish", "ro": "Romanian", "en": "English",
         "ru": "Russian", "de": "German", "other": "Other"}
# Never sent without a person reading it first, whatever the model says.
ALWAYS_HUMAN = {"hardship", "fraud", "complaint", "data_request"}
PROMPT_VERSION = "v1"

SYSTEM = f"""You triage customer emails for a consumer lender that operates in Latvia, Lithuania, Poland, Spain, Peru and Romania.
For each email return JSON only, following the schema.

topic: exactly one of:
{chr(10).join(f"- {k}: {v}" for k, v in TOPICS.items())}
If an email touches two topics, choose the one that needs the most care: fraud > hardship > complaint > data_request > others.
A sarcastic or angry tone alone does not make something a complaint if the actual request is simple.

urgency:
{chr(10).join(f"- {k}: {v}" for k, v in URGENCY.items())}

language: ISO code of the email's language (lv, lt, pl, es, ro, en, ru, de or other).
summary_en: one short English sentence a support lead can scan.
reply: a polite draft reply in the SAME language as the email, 2-4 sentences, signed "Customer Support".
  Never invent amounts, dates, account numbers or decisions: use placeholders like [amount] or [date].
  Never promise to waive fees, delete debt or stop collection. Never give legal advice.
  For fraud: ask them not to pay anything and not to share codes, and say the case is passed to the fraud team.
  For hardship: be warm, say a specialist will contact them about options.
flags: short English tags for anything a human should notice, e.g. "regulator threat", "lawyer", "media threat",
  "possible phishing", "health", "distress", "vulnerable customer", "payment due today". Empty list if none.
confidence: 0 to 1, how sure you are about the topic.
"""

SCHEMA = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "id": {"type": "STRING"},
            "language": {"type": "STRING", "enum": list(LANGS)},
            "topic": {"type": "STRING", "enum": list(TOPICS)},
            "urgency": {"type": "STRING", "enum": list(URGENCY)},
            "summary_en": {"type": "STRING"},
            "reply": {"type": "STRING"},
            "flags": {"type": "ARRAY", "items": {"type": "STRING"}},
            "confidence": {"type": "NUMBER"},
        },
        "required": ["id", "language", "topic", "urgency", "summary_en", "reply", "flags", "confidence"],
    },
}


@dataclass
class Result:
    id: str
    language: str
    topic: str
    urgency: str
    summary_en: str
    reply: str
    flags: list[str] = field(default_factory=list)
    confidence: float = 0.0
    team: str = ""
    needs_human: bool = True
    why_human: str = ""
    source: str = "ai"  # "ai" or "rules"


# ---------------------------------------------------------------- business rules applied after the model

_ESCALATE = re.compile(
    r"ptac|lietuvos bank|rzecznik|banco de españa|banco de espana|anpc|\bbnr\b|ombudsman|abogad|lawyer|advokat|"
    r"adwokat|avocat|social media|redes sociales|policj|policij|policí|polizei",
    re.I,
)


def apply_rules(r: Result, text: str) -> Result:
    r.team = TEAM.get(r.topic, "Customer care")
    if _ESCALATE.search(text) and r.urgency != "high":
        r.urgency = "high"
        if "escalation words" not in r.flags:
            r.flags.append("escalation words")
    reasons = []
    if r.topic in ALWAYS_HUMAN:
        reasons.append(f"{r.topic.replace('_', ' ')} is always reviewed by a person")
    if r.confidence < 0.7:
        reasons.append(f"AI unsure ({r.confidence:.0%})")
    if any(f in r.flags for f in ("distress", "vulnerable customer", "health")):
        reasons.append("vulnerable customer")
    r.needs_human = bool(reasons)
    r.why_human = "; ".join(reasons) if reasons else "simple request: reply can go after a quick check"
    return r


# ---------------------------------------------------------------- AI model (Google Gemini)

class AIError(RuntimeError):
    pass


def pick_model(api_key: str, preferred: str = "") -> str:
    """Ask Google which models this key can use and pick the newest standard Flash model
    (fast and on the free tier). A model named in the app's settings wins if it exists."""
    from google import genai

    client = genai.Client(api_key=api_key)
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions:
            names.append(m.name.removeprefix("models/"))
    if preferred and preferred in names:
        return preferred
    skip = ("lite", "image", "tts", "audio", "live", "embedding", "thinking", "exp", "learnlm", "8b")
    flash = [n for n in names if "flash" in n and not any(x in n for x in skip)]
    if not flash:
        raise AIError(f"No Flash model available for this key. Models found: {', '.join(names[:15])}")

    def rank(n):
        ver = re.findall(r"gemini-(\d+(?:\.\d+)?)", n)
        return ("preview" not in n, float(ver[0]) if ver else 0, n.endswith("latest"), -len(n))

    return max(flash, key=rank)


def triage_ai(emails: list[dict], api_key: str, model: str, batch: int = 8, on_progress=None) -> tuple[list[Result], str]:
    """emails: [{"id", "text"}]. Returns results in the same order, plus the model version used."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    out: dict[str, Result] = {}
    used = model
    for start in range(0, len(emails), batch):
        chunk = emails[start:start + batch]
        payload = json.dumps([{"id": e["id"], "email": e["text"]} for e in chunk], ensure_ascii=False)
        for attempt in range(6):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=f"Triage these {len(chunk)} emails:\n{payload}",
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        response_mime_type="application/json",
                        response_schema=SCHEMA,
                        temperature=0,
                    ),
                )
                used = getattr(resp, "model_version", None) or model
                items = json.loads(resp.text)
                break
            except Exception as e:  # rate limit or a malformed answer: wait and retry
                msg = str(e)
                if attempt == 5:
                    raise AIError(msg[:300]) from e
                wait = 20 if ("429" in msg or "RESOURCE_EXHAUSTED" in msg) else 3
                time.sleep(wait * (attempt + 1) / 2)
        texts = {e["id"]: e["text"] for e in chunk}
        for it in items:
            if it.get("id") not in texts:
                continue
            r = Result(id=it["id"], language=it.get("language", "other"), topic=it.get("topic", "repayment"),
                       urgency=it.get("urgency", "medium"), summary_en=it.get("summary_en", ""),
                       reply=it.get("reply", ""), flags=list(it.get("flags") or []),
                       confidence=float(it.get("confidence") or 0))
            out[r.id] = apply_rules(r, texts[r.id])
        if on_progress:
            on_progress(min(start + batch, len(emails)), len(emails))
    missing = [e["id"] for e in emails if e["id"] not in out]
    if missing:
        raise AIError(f"The model skipped {len(missing)} email(s): {', '.join(missing[:5])}")
    return [out[e["id"]] for e in emails], used


# ---------------------------------------------------------------- baseline: keyword rules, no AI

def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


KEYWORDS = {
    "fraud": ["never taken", "never took", "neesmu nemis", "nekad", "identity", "stolen", "nozaga", "nepateikiau",
              "mano vardu", "na moj pesel", "pesel", "a mi nombre", "pe numele meu", "furat", "phishing", "scam",
              "codigo del sms", "kortel", "never applied", "nigdy"],
    "hardship": ["lost my job", "redundant", "zaudeju darbu", "bedarbis", "stracilem prace", "stracilem", "sin trabajo",
                 "pierdut locul", "divorce", "hospital", "slimnica", "enfermo", "concediu medical", "atlyginimas sumazintas",
                 "nevaresu maksat", "nie dam rady", "nu mai pot"],
    "data_request": ["gdpr", "vdar", "bdar", "rodo", "rgpd", "personas datus", "asmens duomen", "dane osobowe", "danych",
                     "datos personales", "datele mele", "personal data", "marketing", "duomenis"],
    "complaint": ["complaint", "sudzib", "reklamac", "reclamacion", "plangere", "rupjs", "pesima", "ombudsman",
                  "nepatenkint", "nekanie", "explicat"],
    "early_repayment": ["pay off", "settlement", "priekslaicigi", "nomaksat visu", "anksciau", "wczesniej", "cancelar el prestamo",
                        "pago todo antes", "achit integral", "mai devreme", "spłacić", "splacic"],
    "extension": ["extend", "extension", "postpone", "push my next", "pagarinat", "atlikt", "atideti", "pratesti",
                  "przesunac", "przedluzenie", "aplazar", "ampliar el plazo", "amana", "prelungi"],
    "application_status": ["application", "pieteikum", "paraisk", "wniosek", "solicitud", "cererea", "aprobar"],
    "repayment": ["pay", "maksa", "ireiz", "imoka", "rata", "rate", "cuota", "pago", "direct debit", "sumokejau"],
}


def triage_rules(emails: list[dict]) -> list[Result]:
    out = []
    for e in emails:
        t = _fold(e["text"])
        topic = next((k for k, words in KEYWORDS.items() if any(w in t for w in words)), "repayment")
        urg = "high" if topic in ("fraud", "hardship") or re.search(r"rit\b|today|hoy|siandien|dzisiaj|jutro|maine|tomorrow", t) \
            else "low" if topic in ("early_repayment", "application_status", "repayment") else "medium"
        r = Result(id=e["id"], language="other", topic=topic, urgency=urg, summary_en="(keyword rules: no summary)",
                   reply="(keyword rules cannot write replies)", confidence=0.5, source="rules")
        out.append(apply_rules(r, e["text"]))
    return out


# ---------------------------------------------------------------- scoring against the labelled test set

def score(test: list[dict], results: list[Result]) -> dict:
    by_id = {r.id: r for r in results}
    rows = []
    for t in test:
        r = by_id[t["id"]]
        rows.append({
            "id": t["id"], "lang": t["lang"], "text": t["text"], "note": t.get("note", ""),
            "topic_ok": r.topic == t["topic"], "urgency_ok": r.urgency == t["urgency"], "team_ok": r.team == t["team"],
            "lang_ok": r.language == t["lang"],
            "expected": f"{t['topic']} / {t['urgency']} / {t['team']}",
            "got": f"{r.topic} / {r.urgency} / {r.team}",
            # a high-risk email (fraud, hardship, regulator threat) that the system did NOT route to a person
            "missed_risk": t["urgency"] == "high" and not r.needs_human and r.urgency != "high",
        })
    n = len(rows)
    pct = lambda k: sum(x[k] for x in rows) / n
    langs = sorted({x["lang"] for x in rows})
    return {
        "n": n, "topic": pct("topic_ok"), "urgency": pct("urgency_ok"), "team": pct("team_ok"), "language": pct("lang_ok"),
        "missed_risk": sum(x["missed_risk"] for x in rows),
        "by_lang": {l: sum(x["team_ok"] for x in rows if x["lang"] == l) / sum(1 for x in rows if x["lang"] == l) for l in langs},
        "rows": rows,
    }
