import os
import json
import requests
from utils.logger import get_logger

# ✅ Logger centralizzato
logger = get_logger(__name__)

# ✅ Percorso salvataggio token
TOKEN_PATH = "config/token.json"



def is_token_valid(token: str) -> bool:
    url = "https://graph.facebook.com/v18.0/me"
    params = {"access_token": token}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        logger.debug("✅ Token validato correttamente con Meta API.")
        return True
    except requests.exceptions.HTTPError:
        logger.debug("❌ Token non valido.")
        return False


def save_new_token() -> str:
    new_token = input("🔐 Inserisci un nuovo token: ").strip()

    # Salva solo se non esiste già identico
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if data.get("token") == new_token:
                    logger.info("ℹ️ Il token inserito è già quello salvato.")
                    return new_token
            except json.JSONDecodeError:
                pass

    # Crea cartella se non esiste
    os.makedirs(os.path.dirname(TOKEN_PATH), exist_ok=True)

    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump({"token": new_token}, f, indent=2)

    masked_token = f"{new_token[:6]}...{new_token[-4:]}" if len(new_token) > 10 else "token non mascherabile"
    logger.info(f"💾 Nuovo token salvato in {TOKEN_PATH}: {masked_token}")
    return new_token


def load_token() -> str:
    saved_token = None

    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                saved_token = data.get("token")
            except json.JSONDecodeError:
                pass

    if saved_token:
        print("🔐 Token già salvato trovato.")
        choice = input("👉 Vuoi usare il token salvato? (s = sì, n = no): ").strip().lower()

        if choice == "s":
            if is_token_valid(saved_token):
                masked_token = f"{saved_token[:6]}...{saved_token[-4:]}" if len(saved_token) > 10 else "token non mascherabile"
                logger.info(f"🔐 Token valido caricato da {TOKEN_PATH}: {masked_token}")
                return saved_token
            else:
                logger.warning("❌ Il token salvato non è valido o è scaduto.")
                del_choice = input("🗑 Vuoi eliminarlo? (s = sì, n = no): ").strip().lower()
                if del_choice == "s":
                    try:
                        os.remove(TOKEN_PATH)
                        logger.info("✅ Token eliminato.")
                    except Exception as e:
                        logger.error(f"Errore nell'eliminazione del token: {e}")

                next_choice = input("🔁 Vuoi inserire un nuovo token e continuare? (s = sì, n = esci): ").strip().lower()
                if next_choice == "s":
                    return save_new_token()
                else:
                    logger.info("🚪 Uscita dal programma.")
                    exit(0)
        else:
            logger.info("⛔ L'utente ha scelto di non usare il token salvato.")

    # Se il token non esiste o è stato eliminato
    return save_new_token()
