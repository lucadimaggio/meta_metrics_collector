import requests
from utils.logger import get_logger
logger = get_logger(__name__)


def get_instagram_user_id(page_id: str, access_token: str) -> str:
    """
    Recupera l'Instagram user ID collegato a una pagina Facebook.
    Restituisce solo il valore ig_user_id (stringa) oppure None se non trovato.
    Non salva nulla su file.
    """
    url = f"https://graph.facebook.com/v23.0/{page_id}"
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

def run_step2(config: dict) -> dict:
    """
    Esegue lo Step 2: recupera l'Instagram User ID per i Page ID presenti in config,
    aggiorna config con la chiave 'ig_user_id', e restituisce il config aggiornato.

    Parametri:
    - config: dict con almeno le chiavi 'page_ids' (list di stringhe) e 'access_token' (str).

    Ritorna:
    - config aggiornato con 'ig_user_id' (str) o None in caso di errore.
    """
    logger.info("Inizio Step 2 - Recupero Instagram User ID")

    page_ids = config.get("page_ids")
    access_token = config.get("access_token")
    if not page_ids:
        logger.error("Nessun 'page_ids' fornito nel config")
        return config
    if not access_token:
        logger.error("Nessun 'access_token' fornito nel config")
        return config

    ig_user_id = None
    for page_id in page_ids:
        logger.info(f"Recupero IG User ID per Page ID: {page_id}")
        try:
            response = requests.get(
                f"https://graph.facebook.com/v23.0/{page_id}",
                params={
                    "fields": "connected_instagram_account",
                    "access_token": access_token
                }
            )
            logger.debug(f"Risposta API: {response.status_code} - {response.text}")
            response.raise_for_status()

            data = response.json()
            connected_instagram_account = data.get("connected_instagram_account")
            if connected_instagram_account and "id" in connected_instagram_account:
                ig_user_id = connected_instagram_account["id"]
                logger.info(f"IG User ID trovato: {ig_user_id} per Page {page_id}")
                break  # esce al primo ID valido trovato, rimuovi break se vuoi tutti
            else:
                logger.warning(f"Nessun account Instagram collegato alla pagina {page_id}")
        except Exception as e:
            logger.error(f"Errore durante il recupero IG User ID per Page {page_id}: {e}")

    if ig_user_id:
        # Inserisci o aggiorna la chiave 'ig_user_id' in config
        config['ig_user_id'] = ig_user_id
        logger.info(f"Aggiornato config con ig_user_id: {ig_user_id}")
    else:
        logger.warning("Impossibile recuperare IG User ID da nessuna pagina fornita")

    logger.info("Fine Step 2")
    return config



if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Uso: python step2_get_ig_user.py <client_name> <since> <until>")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]

    run(client_name, since, until)
