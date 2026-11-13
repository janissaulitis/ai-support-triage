"""Builds data/test_emails.json: 96 invented customer emails to a fictional consumer lender.

16 per language (Latvian, Lithuanian, Polish, Spanish, Romanian, English), 2 per topic.
Each email carries the answer a careful support lead would give: topic, urgency, team.
Some are deliberately tricky (two topics in one email, no diacritics, sarcasm, wrong language for
the market) so the test measures real-world behaviour, not just easy cases.
"""
import json
from pathlib import Path

TEAM = {
    "repayment": "Customer care",
    "early_repayment": "Customer care",
    "application_status": "Underwriting",
    "extension": "Collections",
    "hardship": "Collections",
    "complaint": "Complaints",
    "data_request": "Compliance",
    "fraud": "Fraud",
}

# (lang, topic, urgency, text, note)
E = [
    # ---------------- Latvian
    ("lv", "repayment", "low", "Labdien! Kur var redzēt, cik man jāmaksā šomēnes un līdz kuram datumam? Līguma nr. L-20481.", ""),
    ("lv", "repayment", "medium", "Samaksāju 15. datumā 86,40 EUR, bet jūsu sistēmā maksājums joprojām nav redzams un atnāca atgādinājums. Lūdzu pārbaudiet.", "payment missing"),
    ("lv", "extension", "high", "Sveiki, vai varu pagarināt aizdevuma termiņu? Maksājums jāveic rīt, bet alga būs tikai nākamnedēļ.", "due tomorrow"),
    ("lv", "extension", "medium", "Vēlos atlikt nākamā mēneša maksājumu uz 2 nedēļām. Cik tas maksās?", ""),
    ("lv", "early_repayment", "low", "Gribu atmaksāt visu aizdevumu priekšlaicīgi. Kāda ir summa šodien un vai procenti tiks pārrēķināti?", ""),
    ("lv", "early_repayment", "low", "vai var nomaksat visu uzreiz bez soda naudas? paldies", "no diacritics"),
    ("lv", "application_status", "low", "Vakar iesniedzu pieteikumu aizdevumam. Kad varētu būt atbilde?", ""),
    ("lv", "application_status", "medium", "Jau 5 dienas gaidu lēmumu par savu pieteikumu, nauda vajadzīga auto remontam. Kas notiek?", "waiting long"),
    ("lv", "hardship", "high", "Zaudēju darbu un nākamos mēnešus nevarēšu maksāt pilnā apmērā. Ko man darīt? Negribu, lai lieta nonāk pie piedziņas.", ""),
    ("lv", "hardship", "high", "Esmu slimnīcā un nevaru veikt maksājumu. Lūdzu, nepiezvaniet maniem radiniekiem.", "health"),
    ("lv", "complaint", "medium", "Jūsu operators pa telefonu bija rupjš un nolika klausuli. Gribu iesniegt sūdzību.", ""),
    ("lv", "complaint", "high", "Jūs man piedzināt divreiz par vienu un to pašu maksājumu. Ja nauda netiks atgriezta 3 dienu laikā, rakstīšu PTAC.", "regulator threat; double charge"),
    ("lv", "data_request", "medium", "Saskaņā ar VDAR lūdzu dzēst visus manus personas datus no jūsu sistēmām.", ""),
    ("lv", "data_request", "medium", "Lūdzu atsūtīt kopiju visiem datiem, ko par mani glabājat, ieskaitot zvanu ierakstus.", ""),
    ("lv", "fraud", "high", "Saņēmu atgādinājumu par aizdevumu, kuru es NEKAD neesmu ņēmis. Kāds ir izmantojis manus datus!", ""),
    ("lv", "fraud", "high", "Man nozaga telefonu ar bankas lietotni, un šodien jūsu kontā redzu jaunu aizdevumu.", ""),
    # ---------------- Lithuanian
    ("lt", "repayment", "low", "Laba diena, kokia sąskaita turiu mokėti įmoką? Sutarties nr. L-31877.", ""),
    ("lt", "repayment", "medium", "Sumokėjau įmoką prieš 4 dienas, bet jūs vis tiek siunčiate priminimus. Prašau patikrinti.", "payment missing"),
    ("lt", "extension", "medium", "Ar galiu atidėti šio mėnesio įmoką vienai savaitei?", ""),
    ("lt", "extension", "high", "Įmoka turi būti sumokėta šiandien, bet negaliu. Ar galima pratęsti terminą?", "due today"),
    ("lt", "early_repayment", "low", "Norėčiau grąžinti visą paskolą anksčiau. Kokia galutinė suma?", ""),
    ("lt", "early_repayment", "low", "Ar yra mokestis, jei grąžinu paskolą anksčiau laiko?", ""),
    ("lt", "application_status", "low", "Pateikiau paraišką vakar vakare. Kada gausiu atsakymą?", ""),
    ("lt", "application_status", "low", "Ar reikia papildomų dokumentų mano paraiškai? Nieko negavau el. paštu.", ""),
    ("lt", "hardship", "high", "Mano atlyginimas sumažintas perpus, nebegaliu mokėti tokių įmokų. Gal galima sumažinti?", ""),
    ("lt", "hardship", "high", "Esu bedarbis jau mėnesį. Prašau nesiųsti skolos išieškotojams, noriu susitarti.", ""),
    ("lt", "complaint", "medium", "Jūsų programėlė nuolat stringa ir negaliu prisijungti jau tris dienas. Labai nepatenkintas.", ""),
    ("lt", "complaint", "high", "Mano paskolos palūkanos neatitinka sutarties. Kreipsiuosi į Lietuvos banką, jei neištaisysite.", "regulator threat"),
    ("lt", "data_request", "medium", "Pagal BDAR prašau ištrinti mano asmens duomenis.", ""),
    ("lt", "data_request", "medium", "Kam perdavėte mano duomenis? Prašau pateikti sąrašą.", ""),
    ("lt", "fraud", "high", "Kažkas pateikė paraišką mano vardu, aš nieko nepateikiau!", ""),
    ("lt", "fraud", "high", "Gavau SMS su nuoroda neva iš jūsų, ten prašė banko kortelės duomenų. Ar tai jūs?", "phishing report"),
    # ---------------- Polish
    ("pl", "repayment", "low", "Dzień dobry, gdzie znajdę numer konta do spłaty raty?", ""),
    ("pl", "repayment", "medium", "Rata została pobrana dwa razy z mojego konta w tym miesiącu. Proszę o wyjaśnienie.", "double charge, polite"),
    ("pl", "extension", "medium", "Czy mogę przesunąć termin spłaty o 14 dni? Ile to będzie kosztować?", ""),
    ("pl", "extension", "high", "Termin płatności mija jutro, a nie dostałem jeszcze wypłaty. Proszę o przedłużenie.", "due tomorrow"),
    ("pl", "early_repayment", "low", "Chciałbym spłacić pożyczkę wcześniej. Jaka jest kwota na dziś?", ""),
    ("pl", "early_repayment", "low", "Czy przy wcześniejszej spłacie odzyskam część odsetek?", ""),
    ("pl", "application_status", "low", "Złożyłem wniosek godzinę temu, kiedy będzie decyzja?", ""),
    ("pl", "application_status", "medium", "Mój wniosek ma status 'w weryfikacji' od tygodnia. Dlaczego tak długo?", "waiting long"),
    ("pl", "hardship", "high", "Straciłem pracę i nie dam rady spłacać rat. Czy jest możliwość rozłożenia długu?", ""),
    ("pl", "hardship", "high", "Mam problemy zdrowotne i komornik już do mnie dzwonił w innej sprawie. Nie dam rady zapłacić w tym miesiącu.", "health; mentions bailiff"),
    ("pl", "complaint", "high", "Składam oficjalną reklamację. Naliczyliście mi opłaty, o których nikt mnie nie informował. Sprawę zgłoszę do Rzecznika Finansowego.", "regulator threat"),
    ("pl", "complaint", "medium", "Wasi konsultanci dzwonią do mnie codziennie o 8 rano. To jest nękanie.", ""),
    ("pl", "data_request", "medium", "Na podstawie RODO żądam usunięcia moich danych osobowych.", ""),
    ("pl", "data_request", "medium", "Proszę o przesłanie kopii moich danych przetwarzanych przez Państwa firmę.", ""),
    ("pl", "fraud", "high", "Ktoś wziął pożyczkę na mój PESEL. Zgłosiłem to już na policję.", ""),
    ("pl", "fraud", "high", "Nie rozpoznaję tej pożyczki w moim profilu BIK, nigdy u was nie byłem klientem.", ""),
    # ---------------- Spanish (Spain and Peru)
    ("es", "repayment", "low", "Hola, ¿cómo puedo pagar la cuota con tarjeta desde la app?", ""),
    ("es", "repayment", "medium", "Hice la transferencia el lunes y todavía aparece como impagada. Adjunto el justificante.", "payment missing"),
    ("es", "extension", "medium", "¿Es posible aplazar el pago de este mes? Cobro a final de mes.", ""),
    ("es", "extension", "high", "Hoy vence mi cuota y no llego. ¿Puedo ampliar el plazo unos días?", "due today"),
    ("es", "early_repayment", "low", "Quiero cancelar el préstamo por completo. ¿Cuánto debo exactamente?", ""),
    ("es", "early_repayment", "low", "Buenas, si pago todo antes, ¿me descuentan intereses?", "Peru"),
    ("es", "application_status", "low", "Envié mi solicitud ayer, ¿cuándo recibiré respuesta?", ""),
    ("es", "application_status", "medium", "¿Necesitan algún documento más para aprobar mi solicitud? Me llegó un correo raro.", "strange email: possible phishing (label corrected after the AI flagged it)"),
    ("es", "hardship", "high", "Me quedé sin trabajo y no puedo pagar. Por favor, no me llamen más, quiero buscar una solución.", ""),
    ("es", "hardship", "high", "Estoy enfermo y con muchas deudas, no sé cómo voy a pagar esto. Estoy desesperado.", "distress"),
    ("es", "complaint", "medium", "Su atención al cliente es pésima, nadie contesta el teléfono.", ""),
    ("es", "complaint", "high", "Me cobraron una comisión ilegal. Si no la devuelven, presentaré una reclamación ante el Banco de España y mi abogado se pondrá en contacto.", "regulator + lawyer"),
    ("es", "data_request", "medium", "Ejerzo mi derecho de supresión según el RGPD. Borren todos mis datos.", ""),
    ("es", "data_request", "medium", "Solicito acceso a mis datos personales y a la grabación de la llamada del día 3.", "Peru"),
    ("es", "fraud", "high", "Alguien ha solicitado un préstamo a mi nombre con mi DNI. Yo no he sido.", ""),
    ("es", "fraud", "high", "Me llamaron diciendo que eran de ustedes y me pidieron el código del SMS. ¿Era real?", "social engineering"),
    # ---------------- Romanian
    ("ro", "repayment", "low", "Bună ziua, în ce cont trebuie să plătesc rata?", ""),
    ("ro", "repayment", "medium", "Am plătit rata acum 3 zile, dar în aplicație apare că am restanță.", "payment missing"),
    ("ro", "extension", "medium", "Pot amâna plata ratei cu două săptămâni?", ""),
    ("ro", "extension", "high", "Scadența este mâine și nu am banii. Se poate prelungi termenul?", "due tomorrow"),
    ("ro", "early_repayment", "low", "Aș dori să achit integral creditul. Care este suma totală?", ""),
    ("ro", "early_repayment", "low", "Daca platesc mai devreme, se recalculeaza dobanda?", "no diacritics"),
    ("ro", "application_status", "low", "Am trimis cererea ieri. Când primesc un răspuns?", ""),
    ("ro", "application_status", "medium", "Aștept de 6 zile aprobarea și am nevoie urgent de bani pentru chirie.", "waiting long"),
    ("ro", "hardship", "high", "Mi-am pierdut locul de muncă și nu mai pot plăti ratele. Ce opțiuni am?", ""),
    ("ro", "hardship", "high", "Sunt în concediu medical și venitul meu a scăzut mult. Vă rog să nu trimiteți datoria la recuperatori.", ""),
    ("ro", "complaint", "medium", "Am fost taxat cu un comision pe care nu l-am înțeles. Vreau explicații.", "soft complaint"),
    ("ro", "complaint", "high", "Voi depune plângere la ANPC și la BNR dacă nu opriți apelurile zilnice.", "regulator threat"),
    ("ro", "data_request", "medium", "Conform GDPR, vă solicit ștergerea tuturor datelor mele personale.", ""),
    ("ro", "data_request", "medium", "Vreau o copie a datelor mele și să știu cui le-ați transmis.", ""),
    ("ro", "fraud", "high", "Cineva a luat un credit pe numele meu, eu nu am aplicat niciodată!", ""),
    ("ro", "fraud", "high", "Mi-a fost furată cartea de identitate săptămâna trecută. Vă rog blocați orice cerere pe numele meu.", "pre-emptive block"),
    # ---------------- English (expats, mixed)
    ("en", "repayment", "low", "Hi, can I change the day of the month my instalment is taken?", ""),
    ("en", "repayment", "medium", "My direct debit failed even though there was money in the account. Will I be charged a late fee?", ""),
    ("en", "extension", "medium", "Is it possible to push my next payment back by a week?", ""),
    ("en", "extension", "high", "Payment is due TODAY and my salary is late. Can I get a few days' extension please?", "due today"),
    ("en", "early_repayment", "low", "I'd like to pay off the remaining balance. Please send the settlement amount.", ""),
    ("en", "early_repayment", "low", "Oh great, another fee. Do you also charge me for paying you back early? Just tell me the total.", "sarcastic tone, but a simple question"),
    ("en", "application_status", "low", "Just applied, how long does approval usually take?", ""),
    ("en", "application_status", "medium", "My application has been 'pending' for a week and nobody answers. I need to know today.", "waiting long"),
    ("en", "hardship", "high", "I was made redundant last month. I want to keep paying but I need a smaller monthly amount.", ""),
    ("en", "hardship", "high", "Going through a divorce and can't cover the payments right now. Please don't pass this to a debt collector.", ""),
    ("en", "complaint", "medium", "The interest on my statement doesn't match what I was told when I signed. Please explain.", "mild"),
    ("en", "complaint", "high", "Third email with no answer. I'm forwarding this to the financial ombudsman and posting on social media.", "regulator + public"),
    ("en", "data_request", "medium", "Under GDPR I request a copy of all personal data you hold about me.", ""),
    ("en", "data_request", "medium", "Please stop using my data for marketing and confirm in writing.", ""),
    ("en", "fraud", "high", "There's a loan on my account I never took out. I think my identity was stolen.", ""),
    ("en", "fraud", "high", "Paid my instalment to the account number in your email, but your support says it's not yours. Was I scammed?", "payment to fake account: fraud, not repayment"),
]


def main():
    rows = []
    for i, (lang, topic, urgency, text, note) in enumerate(E, 1):
        rows.append({"id": f"E{i:03d}", "lang": lang, "text": text, "topic": topic,
                     "urgency": urgency, "team": TEAM[topic], "note": note})
    assert len(rows) == 96, len(rows)
    out = Path(__file__).with_name("test_emails.json")
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} emails -> {out}")


if __name__ == "__main__":
    main()
