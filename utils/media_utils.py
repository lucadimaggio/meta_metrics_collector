### FILE: utils/media_utils.py
import requests
import subprocess
from pathlib import Path
from tqdm import tqdm
from utils.logger import get_logger, log_exceptions

logger = get_logger(__name__)


@log_exceptions
def download_file(url, path, retries=3):
    """
    Scarica un file da un URL remoto e lo salva nel percorso specificato.
    Riprova fino a 'retries' volte in caso di errore.
    Mostra una barra di progresso con il nome del file (non l'intero URL).
    Gestisce il caso in cui content-length non sia disponibile.
    """
    path = Path(path)  # assicurarsi che path sia un Path object per .name
    for attempt in range(1, retries + 1):
        logger.debug(f"Tentativo {attempt}/{retries} - Download da URL: {url} -> {path}")
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            total_size = response.headers.get('content-length')
            if total_size is not None:
                total_size = int(total_size)
            else:
                total_size = None  # tqdm gestirà barra senza dimensione

            with open(path, 'wb') as f, tqdm(
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                desc=path.name,
                leave=True,
            ) as bar:
                for chunk in response.iter_content(8192):
                    if chunk:
                        f.write(chunk)
                        bar.update(len(chunk))

            logger.info(f"✅ Download completato: {path}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Errore download {url}: {e}")
            if attempt == retries:
                logger.error(f"❌ Fallimento download dopo {retries} tentativi")
                return False


@log_exceptions
def extract_frame(video_path, frame_path):
    command = [
        "ffmpeg",
        "-i", video_path,
        "-vf", "select=eq(n\\,0)",
        "-q:v", "3",
        "-frames:v", "1",
        frame_path
    ]
    try:
        subprocess.run(command, check=True, capture_output=True)
        logger.info(f"✅ Frame estratto: {frame_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Errore estrazione frame: {e}")
        if e.stderr:
            logger.debug(f"ffmpeg stderr: {e.stderr.decode('utf-8')}")
        return False


@log_exceptions
def get_carousel_first_image(media_id, access_token):
    url = f"https://graph.facebook.com/v20.0/{media_id}/children"
    params = {
        "fields": "media_type,media_url",
        "access_token": access_token
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        for child in data.get("data", []):
            if child.get("media_type") == "IMAGE":
                logger.debug(f"Immagine trovata nel carosello: {child['media_url']}")
                return child["media_url"]
        logger.warning("⚠️ Nessuna immagine trovata nel carosello")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Errore durante il recupero dell'immagine del carosello: {e}")
        return None
