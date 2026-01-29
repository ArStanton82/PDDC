import streamlit as st
import os
from openai import OpenAI
from dotenv import load_dotenv
import pymupdf  # PyMuPDF per estrazione base
import pdfplumber  # per tabelle e testo strutturato

# Carica variabili d'ambiente
load_dotenv()
VENICE_API_KEY = os.getenv("VENICE_API_KEY")
if not VENICE_API_KEY:
    st.error("Chiave API Venice non trovata. Verifica il file .env con VENICE_API_KEY.")
    st.stop()

client = OpenAI(
    api_key=VENICE_API_KEY,
    base_url="https://api.venice.ai/api/v1"
)

# Login semplice (prototipo – modifica credenziali in produzione)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Accesso al Tool di Verifica Coerenza PDDC")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Accedi"):
        if username == "admin" and password == "pddc2026":  # Cambia immediatamente!
            st.session_state.authenticated = True
            st.success("Accesso effettuato correttamente.")
            st.rerun()
        else:
            st.error("Credenziali non valide.")
    st.stop()

# Interfaccia principale
st.title("Verifica Coerenza Interna tra PDDC e Allegati")

pddc_file = st.file_uploader("Carica il file PDDC principale (PDF)", type=["pdf"])
allegati_files = st.file_uploader("Carica gli allegati (PDF multipli)", type=["pdf"], accept_multiple_files=True)

if st.button("Avvia Analisi") and pddc_file:
    with st.spinner("Estrazione testo dai documenti..."):
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

    # Prompt ottimizzato per Gemma 3 27B
    prompt = f"""
Analisi di conformità interna per atti di affidamento pubblico.

TESTO PDDC PRINCIPALE:
{pddc_text[:12000]}  # limite conservativo per contesto

ALLEGATI ESTRATTI:
"""

    for nome, testo in allegati_testi.items():
        prompt += f"\n--- ALLEGATO: {nome} ---\n{testo[:6000]}\n"

prompt = f"""
Ruolo: Sei un esperto funzionario amministrativo specializzato in procedure di affidamento pubblico (D.Lgs. 36/2023). Il tuo unico compito è verificare la coerenza interna tra la Proposta/Determina a Contrarre (PDDC) e i suoi allegati estratti, senza esprimere giudizi normativi generali.

Contesto: Devi controllare SOLO la corrispondenza interna tra documento principale e allegati.

Elementi da verificare (in ordine):
1. Oggetto dell'affidamento: corrispondenza testuale o sostanziale.
2. Importo stimato / valore economico: corrispondenza numerica (tolleranza ±1%).
3. Contraente / operatore economico: nome, P.IVA o riferimenti coincidono.
4. Motivazione scelta procedura/contraente: supportata da allegati concreti (es. preventivi comparati).
5. Elementi essenziali: CIG/CUP, RUP, durata, copertura finanziaria, luogo di esecuzione coincidono.

Ragionamento obbligatorio (Chain-of-Thought):
1. Identifica gli elementi chiave dalla PDDC.
2. Confronta ciascun elemento con gli allegati.
3. Segnala discrepanze con spiegazione precisa.
4. Assegna esito complessivo.

Esempi few-shot (usa come riferimento):
Esempio 1:
PDDC: Oggetto "Fornitura carta A4", Importo 5.000 €, Contraente "Carta Srl P.IVA 01234567890"
Allegato 1: Preventivo "Fornitura carta A4" per 5.000 €
Allegato 2: Preventivo "Carta Srl" per 5.000 €
Output atteso: {{"esito_complessivo": "CONFORME", "criticita": [{"elemento": "Oggetto", "esito": "OK", "spiegazione": "Corrispondenza esatta"}, ...]}}

Esempio 2:
PDDC: Importo 10.000 €
Allegato 1: Totale 9.500 €
Output atteso: {{"esito_complessivo": "CONFORME CON RISERVE", "criticita": [{"elemento": "Importo", "esito": "WARNING", "spiegazione": "Differenza del 5%, tolleranza superata"}]}} 

TESTO PDDC PRINCIPALE:
{pddc_text[:12000]}

ALLEGATI ESTRATTI:
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

    with st.spinner("Analisi con Google Gemma 3 27B Instruct in corso..."):
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
