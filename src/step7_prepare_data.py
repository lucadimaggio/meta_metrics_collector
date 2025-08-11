import os
import json
from tqdm import tqdm
from utils.logger import get_logger, log_exceptions
from src.step6_prepare_images import download_file

logger = get_logger(__name__)

@log_exceptions
def prepare_data(client_name, since, until):
    """
    Carica il JSON con i dati post,
    scarica i media se confermato dall'utente,
    aggiorna i percorsi locali e salva JSON aggiornato.
    NON genera PDF.
    """
    json_path = f"output/{client_name}/pdf_fields_{since}_{until}_with_images.json"
    download_dir = f"media/{client_name}"

    logger.info(f"Caricamento file JSON: {json_path}")
    if not os.path.exists(json_path):
        logger.error(f"File JSON non trovato: {json_path}")
        return False

    with open(json_path, "r", encoding="utf-8") as f:
        top_posts = json.load(f)

    if not isinstance(top_posts, list) or len(top_posts) == 0:
        logger.error("Nessun top post trovato nel JSON o formato errato (lista attesa).")
        return False

    download_paths = [post.get("media_url") for post in top_posts if post.get("media_url")]
    if not download_paths:
        logger.warning("Nessun media da scaricare.")
        return False

    logger.info("📸 Media da scaricare:")
    for i, path in enumerate(download_paths, 1):
        logger.info(f"{i}. {path}")

    risposta = input("Vuoi procedere con il download? (s/n): ").strip().lower()
    if risposta != "s":
        logger.info("Download annullato dall'utente.")
        return False

    os.makedirs(download_dir, exist_ok=True)

    downloaded_files = 0
    skipped_files = 0

    for url in tqdm(download_paths, desc="Download media", unit="file"):
        filename = os.path.basename(url.split("?")[0])
        filepath = os.path.join(download_dir, filename)
        if os.path.exists(filepath):
            logger.info(f"File già presente, skip download: {filename}")
            skipped_files += 1
        else:
            tqdm.write(f"⬇ Downloading: {filename}")
            try:
                success = download_file(url, filepath)
                if success:
                    logger.debug(f"Scaricato {filename}")
                    downloaded_files += 1
                else:
                    logger.warning(f"Download fallito per {url}")
            except Exception as e:
                logger.error(f"Errore durante download di {url}: {e}")

        # Aggiorna local_img_path nel post corrispondente
        for post in top_posts:
            if post.get("local_img_path") == url:
                post["local_img_path"] = filepath

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(top_posts, f, ensure_ascii=False, indent=4)
    logger.info("JSON aggiornato con i percorsi locali delle immagini.")
    logger.info(f"Download completato: {downloaded_files} file scaricati, {skipped_files} file saltati.")

    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        logger.error("Usage: python src/step7_prepare_data.py <client_name> <since> <until>")
        logger.info("Example: python src/step7_prepare_data.py 55Bijoux 2025-07-01 2025-07-25")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]
    prepare_data(client_name, since, until)
