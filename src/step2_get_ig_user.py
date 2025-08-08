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
            ig_account = data["connected_instagram_account"]
            if ig_account is not None and "id" in ig_account:
                ig_id = ig_account["id"]
                logger.info(f"[✅] IG User ID per Page {page_id}: {ig_id}")
                return ig_id
            else:
                logger.warning(f"[⚠️] Collegamento Instagram presente ma ID mancante per pagina {page_id}")
                return None
        else:
            logger.warning(f"[⚠️] Nessun account Instagram collegato alla pagina {page_id}")
            return None

    except requests.exceptions.HTTPError as e:
        logger.error(f"[❌] Errore HTTP durante il recupero di IG User ID per Page {page_id}: {e}")
        logger.error(f"[ℹ️] Risposta: {response.text}")
        return None
    except Exception as e:
        logger.error(f"[❌] Errore generico durante il recupero di IG User ID per Page {page_id}: {e}")
        return None

import sys

def run(client_name, since, until):
    from utils.token_utils import load_token
    from utils.client_utils import load_client_data, save_client_data

    logger.info(f"Step 2 - Recupero IG User ID per cliente {client_name} da {since} a {until}")

    access_token = load_token()
    if not access_token:
        logger.error("Access token non disponibile o non caricato correttamente.")
        return

    client_data = load_client_data(client_name)
    if not client_data:
        logger.error(f"Nessun dato Page ID trovato per il cliente '{client_name}'.")
        return

    for page_id in client_data.keys():
        logger.info(f"Recupero IG User ID per Facebook Page ID: {page_id}")
        ig_user_id = get_instagram_user_id(page_id, access_token)

        if ig_user_id:
            logger.info(f"Salvataggio IG User ID per cliente '{client_name}', pagina {page_id}")
            save_client_data(client_name, page_id, ig_user_id)
        else:
            logger.warning(f"Impossibile recuperare IG User ID per pagina {page_id}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python step2_get_ig_user.py <client_name> <since> <until>")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]

    run(client_name, since, until)
