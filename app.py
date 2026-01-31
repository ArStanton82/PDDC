import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
import pymupdf  # PyMuPDF
import pdfplumber

# ────────────────────────────────────────────────────────────────
# Caricamento variabili d'ambiente / Secrets
# ────────────────────────────────────────────────────────────────

load_dotenv()  # utile in locale con file .env

VENICE_API_KEY = os.getenv("VENICE_API_KEY")
APP_USERNAME   = os.getenv("APP_USERNAME")
APP_PASSWORD   = os.getenv("APP_PASSWORD")

if not VENICE_API_KEY:
    st.error("Chiave API Venice non trovata. Verifica i Secrets di Streamlit Cloud o il file .env.")
    st.stop()

if not APP_USERNAME or not APP_PASSWORD:
    st.warning("Credenziali di login non configurate nei Secrets. L'accesso è aperto a tutti per test.")
    # Se vuoi bloccare completamente quando mancano le credenziali, decommenta le righe seguenti:
    # st.error("APP_USERNAME e/o APP_PASSWORD non definiti nei Secrets.")
    # st.stop()

client = OpenAI(
    api_key=VENICE_API_KEY,
    base_url="https://api.venice.ai/api/v1"
)

# ────────────────────────────────────────────────────────────────
# Autenticazione basata su variabili d'ambiente / Secrets
# ────────────────────────────────────────────────────────────────

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Accesso al Tool di Verifica Coerenza PDDC")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Accedi"):
        if username == APP_USERNAME and password == APP_PASSWORD:
            st.session_state.authenticated = True
            st.success("Accesso effettuato correttamente.")
            st.rerun()
        else:
            st.error("Credenziali non valide.")

    st.stop()  # blocca tutto il resto finché non si è autenticati

# ────────────────────────────────────────────────────────────────
# Interfaccia principale – solo dopo login riuscito
# ────────────────────────────────────────────────────────────────

st.title("Verifica Coerenza Interna tra PDDC e Allegati")

pddc_file = st.file_uploader("Carica il file PDDC principale (PDF)", type=["pdf"])
allegati_files = st.file_uploader("Carica gli allegati (PDF multipli)", type=["pdf"], accept_multiple_files=True)

if st.button("Avvia Analisi") and pddc_file:
    with st.spinner("Estrazione testo dai documenti…"):
        # Estrazione testo PDDC
        pddc_text = ""
        doc = pymupdf.open(stream=pddc_file.read(), filetype="pdf")
        for page in doc:
            pddc_text += page.get_text("text") + "\n"
        doc.close()

        # Estrazione testi allegati
        allegati_testi = {}
        for allegato in allegati_files:
            allegato.seek(0)
            nome = allegato.name
            testo = ""
            try:
                with pdfplumber.open(allegato) as pdf:
                    for page in pdf.pages:
                        testo += (page.extract_text() or "") + "\n"
            except Exception as e:
                testo = f"Errore estrazione: {str(e)}"
            allegati_testi[nome] = testo

    st.success("Estrazione completata.")

    # ────────────────────────────────────────────────────────────────
    # Prompt engineering avanzato
    # ────────────────────────────────────────────────────────────────

    prompt = f"""
Ruolo: Sei un esperto funzionario amministrativo specializzato in procedure di affidamento pubblico (D.Lgs. 36/2023).  
Il tuo unico compito è verificare la **coerenza interna e la pertinenza** tra la Proposta/Determina a Contrarre (PDDC) e i suoi allegati estratti.

Regola fondamentale:  
- Gli allegati devono essere **chiaramente riferiti alla stessa procedura/oggetto** descritto nella PDDC.  
- Se un allegato appare estraneo, non correlato o appartenente a un'altra pratica (es. diverso oggetto, diverso contraente, diverso CIG/CUP), l'esito complessivo deve essere **NON CONFORME** con motivazione esplicita.

Ragionamento obbligatorio (Chain-of-Thought – segui esattamente quest'ordine):
1. Valuta la pertinenza globale di ciascun allegato rispetto alla PDDC (oggetto principale, CIG/CUP, contraente, riferimenti normativi).  
   → Se non è pertinente → termina con esito NON CONFORME.
2. Solo se tutti gli allegati sono pertinenti, procedi al confronto dettagliato degli elementi.
3. Identifica gli elementi chiave dalla PDDC.
4. Confronta ciascun elemento con gli allegati.
5. Segnala ogni discrepanza con spiegazione precisa.
6. Assegna esito complessivo.

Elementi da verificare (solo se pertinenti):
1. Oggetto dell'affidamento: corrispondenza testuale o sostanziale.
2. Importo stimato / valore economico: corrispondenza numerica (tolleranza ±1%).
3. Contraente / operatore economico: nome, P.IVA o riferimenti coincidono.
4. Motivazione scelta procedura/contraente: supportata da allegati concreti.
5. Elementi essenziali: CIG/CUP, RUP, durata, copertura finanziaria, luogo coincidono.

TESTO PDDC PRINCIPALE:
{pddc_text[:12000]}

ALLEGATI ESTRATTI:
"""

    for nome, testo in allegati_testi.items():
    prompt += f"\n--- ALLEGATO: {nome} ---\n{testo[:6000]}\n"

prompt += """
Output SOLO JSON valido, senza testo aggiuntivo:
{
  "esito_complessivo": "CONFORME" | "CONFORME CON RISERVE" | "NON CONFORME",
  "pertinenza_allegati": [{"nome_allegato": "...", "pertinente": true/false, "motivazione": "..."}],
  "criticita": [
    {"elemento": "...", "esito": "OK"|"WARNING"|"ERROR", "spiegazione": "..."}
  ],
  "dettagli": "Riassunto sintetico della verifica"
}
"""

    for nome, testo in allegati_testi.items():
        prompt += f"\n--- ALLEGATO: {nome} ---\n{testo[:6000]}\n"

    prompt += """
Output SOLO JSON valido, senza testo aggiuntivo o commenti esterni:
{
  "esito_complessivo": "CONFORME" | "CONFORME CON RISERVE" | "NON CONFORME",
  "criticita": [
    {"elemento": "Oggetto"|"Importo"|"Contraente"|"Motivazione"|"CIG/CUP"|"RUP"|"Durata"|"Altro", "esito": "OK"|"WARNING"|"ERROR", "spiegazione": "..."}
  ],
  "dettagli": "Riassunto sintetico della verifica"
}
"""

    with st.spinner("Analisi con Google Gemma 3 27B Instruct in corso…"):
        try:
            response = client.chat.completions.create(
                model="google-gemma-3-27b-it",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )
            report_json = response.choices[0].message.content
            st.subheader("Report di Verifica Coerenza")
            st.json(report_json)
            st.info(f"Token utilizzati: {response.usage.total_tokens}")
        except Exception as e:
            st.error(f"Errore durante l'analisi API: {str(e)}")
            st.info("Verifica crediti/tier Pro su Venice.ai o prova con modello alternativo.")
