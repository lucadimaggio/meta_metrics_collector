import os
import json
import logging
from typing import List, Dict, Any
from typing import Optional


logger = logging.getLogger(__name__)


def save_media_as_json(
    all_media: List[Dict[str, Any]],
    client_name: str,
    since: str,
    until: str,
    output_path: str = None
) -> None:
    """
    Salva la lista completa dei media in formato JSON.
    Se output_path è fornito, salva lì il file JSON, altrimenti salva in media/{client_name}.
    """
    try:
        logger.info(f"Salvataggio JSON media avviato per {client_name} dal {since} al {until}")

        if output_path is None:
            folder_path = os.path.join("media", client_name)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, f"raw_media_{since}_{until}.json")
        else:
            folder_path = os.path.dirname(output_path)
            os.makedirs(folder_path, exist_ok=True)
            file_path = output_path

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(all_media, f, ensure_ascii=False, indent=2)

        logger.info(f"[💾] Media JSON salvato in {file_path} ({len(all_media)} record)")

    except Exception as e:
        logger.error(f"Errore durante il salvataggio JSON per {client_name}: {e}")





def save_text_report(report_text: str, client_name: str, since: str, until: str, report_name: str) -> None:
    """
    Salva un report testuale in un file .txt nella cartella output per il cliente.
    """
    try:
        logger.info(f"Salvataggio report testuale '{report_name}' avviato per {client_name}")
        folder_path = os.path.join("output", client_name)
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, f"{report_name}_{since}_{until}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        logger.info(f"[💾] Report '{report_name}' salvato in {file_path}")

    except Exception as e:
        logger.error(f"Errore durante il salvataggio del report '{report_name}' per {client_name}: {e}")


def save_reel_duration_report(report_text: str, client_name: str, since: str, until: str) -> None:
    """
    Salva il report testuale della durata media dei reel/video.
    """
    try:
        logger.info(f"Salvataggio report durata reel avviato per {client_name}")
        folder_path = os.path.join("output", client_name)
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, f"reel_duration_report_{since}_{until}.txt")

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        logger.info(f"[💾] Report durata reel salvato in {file_path}")

    except Exception as e:
        logger.error(f"Errore durante il salvataggio del report durata reel per {client_name}: {e}")


def save_integrated_analysis_report(analysis_data: Dict[str, Any], client_name: str, since: str, until: str) -> None:
    """
    Salva un report integrato delle analisi contenuti in formato JSON.
    """
    try:
        logger.info(f"Salvataggio report integrato avviato per {client_name}")
        folder_path = os.path.join("output", client_name)
        os.makedirs(folder_path, exist_ok=True)

        file_path = os.path.join(folder_path, f"integrated_analysis_{since}_{until}.json")

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(analysis_data, f, ensure_ascii=False, indent=2)

        logger.info(f"[💾] Report integrato salvato in {file_path}")

    except Exception as e:
        logger.error(f"Errore durante il salvataggio del report integrato per {client_name}: {e}")


def load_media_from_json(client_name: str, since: str, until: str) -> List[Dict[str, Any]]:
    """
    Carica i media precedentemente salvati da un file JSON.
    """
    try:
        file_path = os.path.join("media", client_name, f"raw_media_{since}_{until}.json")
        logger.info(f"Caricamento media JSON da {file_path}")

        if not os.path.exists(file_path):
            logger.warning(f"Nessun file JSON trovato in {file_path}")
            return []

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        logger.info(f"[📂] Media JSON caricato da {file_path} ({len(data)} record)")
        return data

    except Exception as e:
        logger.error(f"Errore durante il caricamento JSON per {client_name}: {e}")
        return []
