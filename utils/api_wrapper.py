import requests
import time
from typing import Any, Dict, Optional

from utils.logger import get_logger, log_exceptions

# Istanzia il logger locale
logger = get_logger(__name__)

# Timeout e configurazione retry
TIMEOUT = 10  # secondi
MAX_RETRIES = 3
RETRY_DELAY = 2  # secondi tra i retry per errori transient


def handle_transient_error(data: Dict[str, Any], attempt: int, method: str) -> bool:
    """
    Restituisce True se l'errore è transient e vale la pena ritentare.
    Logga warning o error a seconda se sia ultimo tentativo.
    """
    err = data.get("error", {})
    if isinstance(err, dict) and err.get("is_transient") is True:
        if attempt < MAX_RETRIES:
            logger.warning(
                f"{method} transient error rilevato (tentativo {attempt}), riprovo in {RETRY_DELAY}s..."
            )
            return True
        else:
            logger.error(
                f"{method} transient error all'ultimo tentativo ({attempt}), interrompo."
            )
            return False
    return False


@log_exceptions
def get(url: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """
    Esegue una chiamata GET all'API Meta.
    Restituisce il payload JSON.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        logger.debug(f"Chiamata API: GET {url} params={params}")
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
        except requests.RequestException as e:
            logger.error(f"Errore nella chiamata API {url}: {e}")
            raise

        logger.debug(f"Risposta API {response.status_code}: {response.text}")

        if response.status_code >= 400:
            logger.error(f"Errore API {response.status_code}: {response.text}")
            try:
                error_data = response.json().get("error", {"message": response.text, "code": response.status_code})
            except Exception:
                error_data = {"message": response.text, "code": response.status_code}
            return {"error": error_data}
        
        try:
            data = response.json()
        except ValueError as e:
            logger.error(f"Errore parsing JSON da {url}: {e}")
            raise

        # Gestione transient error
        if handle_transient_error(data, attempt, "GET"):
            time.sleep(RETRY_DELAY)
            continue

        return data

    # Se si esce dal loop senza return, solleva
    raise RuntimeError(f"GET {url} fallito dopo {MAX_RETRIES} tentativi transient")


@log_exceptions
def post(url: str, data: Optional[Dict[str, Any]] = None) -> Any:
    """
    Esegue una chiamata POST all'API Meta.
    Restituisce il payload JSON.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        logger.debug(f"Chiamata API: POST {url} data={data}")
        try:
            response = requests.post(url, json=data, timeout=TIMEOUT)
        except requests.RequestException as e:
            logger.error(f"Errore nella chiamata API {url}: {e}")
            raise

        logger.debug(f"Risposta API {response.status_code}: {response.text}")

        if response.status_code >= 400:
            logger.error(f"Errore API {response.status_code}: {response.text}")
            try:
                error_data = response.json().get("error", {"message": response.text, "code": response.status_code})
            except Exception:
                error_data = {"message": response.text, "code": response.status_code}
            return {"error": error_data}

        try:
            payload = response.json()
        except ValueError as e:
            logger.error(f"Errore parsing JSON da {url}: {e}")
            raise

        # Gestione transient error
        if handle_transient_error(payload, attempt, "POST"):
            time.sleep(RETRY_DELAY)
            continue

        return payload

    # Se si esce dal loop senza return, solleva
    raise RuntimeError(f"POST {url} fallito dopo {MAX_RETRIES} tentativi transient")
