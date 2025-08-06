import requests
from utils.logger import get_logger
logger = get_logger(__name__)


def get_instagram_user_id(page_id: str, access_token: str) -> str:
    """
    Recupera l'Instagram user ID collegato a una pagina Facebook.
    Restituisce solo il valore ig_user_id (stringa) oppure None se non trovato.
    Non salva nulla su file.
    """
    url = f"https://graph.facebook.com/v18.0/{page_id}"
    params = {
        "fields": "connected_instagram_account",
        "access_token": access_token
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if "connected_instagram_account" in data:
            ig_id = data["connected_instagram_account"]["id"]
            print(f"[✅] IG User ID per Page {page_id}: {ig_id}")
            return ig_id
        else:
            print(f"[⚠️] Nessun account Instagram collegato alla pagina {page_id}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"[❌] Errore HTTP durante il recupero di IG User ID per Page {page_id}: {e}")
        print(f"[ℹ️] Risposta: {response.text}")
        return None
    except Exception as e:
        print(f"[❌] Errore generico durante il recupero di IG User ID per Page {page_id}: {e}")
        return None

import sys

def run(client_name, since, until):
    # Qui inserisci la logica attuale per recuperare IG User ID
    print(f"Step 2 - Recupero IG User ID per cliente {client_name} da {since} a {until}")
    # TODO: sostituisci con il codice reale di chiamata API e gestione dati

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python step2_get_ig_user.py <client_name> <since> <until>")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]

    run(client_name, since, until)
