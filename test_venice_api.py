import os
from openai import OpenAI
from dotenv import load_dotenv

# Carica esplicitamente .env dalla directory corrente
load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'), override=True)

# Debug: stampa tutte le variabili rilevanti
print("Debug: percorso cwd:", os.getcwd())
print("Debug: VENICE_API_KEY da getenv:", os.getenv("VENICE_API_KEY"))
print("Debug: OPENAI_API_KEY da getenv:", os.getenv("OPENAI_API_KEY"))

api_key = os.getenv("VENICE_API_KEY")
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")  # fallback per test
    if not api_key:
        raise ValueError(
            "VENICE_API_KEY (o OPENAI_API_KEY) non trovata. "
            "Verifica: 1) file .env esiste e contiene VENICE_API_KEY=valore_senza_virgolette\n"
            "2) Esegui 'source .env' o 'export VENICE_API_KEY=...' prima di lanciare Python\n"
            "3) Nessun spazio o carattere extra nel file .env"
        )

print("Chiave rilevata:", api_key[:10] + "..." + api_key[-6:])  # maschera per sicurezza

client = OpenAI(
    api_key=api_key,
    base_url="https://api.venice.ai/api/v1"
)

# Test chiamata
response = client.chat.completions.create(
    model="venice-uncensored",
    messages=[
        {"role": "user", "content": "Ciao! Conferma che sei Venice.ai e dimmi il modello usato."}
    ],
    temperature=0.0,
    max_tokens=100
)

print("\nRisposta del modello:")
print(response.choices[0].message.content.strip())
print("\nUso token:", response.usage)
