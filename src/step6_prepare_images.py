import os
import sys
import json
from pathlib import Path
from tqdm import tqdm
from utils.logger import get_logger, log_exceptions
from utils.media_utils import download_file, extract_frame, get_carousel_first_image

logger = get_logger(__name__)

# CONFIGURAZIONE INIZIALE
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_DIR = BASE_DIR / "media"
OUTPUT_DIR = BASE_DIR / "output"


# SCRIPT PRINCIPALE
@log_exceptions
def main(client_name, since, until, access_token):
    logger.info(f"Esecuzione step6_prepare_images per {client_name} dal {since} al {until}")

    client_output = OUTPUT_DIR / client_name
    json_input = client_output / f"pdf_fields_{since}_{until}_with_images.json"
    json_output = client_output / f"pdf_fields_{since}_{until}_with_images.json"

    if not json_input.exists():
        logger.error(f"File JSON non trovato: {json_input}")
        sys.exit(1)

    logger.info(f"Caricamento JSON input: {json_input}")
    with open(json_input, encoding='utf-8') as f:
        posts = json.load(f)

    if not posts:
        logger.warning("Nessun post trovato nel JSON.")
        sys.exit(0)

    logger.info(f"Campi trovati: {', '.join(posts[0].keys())}")

    client_media_dir = MEDIA_DIR / client_name
    client_media_dir.mkdir(parents=True, exist_ok=True)

    downloaded = []
    failed = []
    total_posts = len(posts)

    for idx, post in enumerate(posts, 1):
        filename_base = f"post_{idx}"

        # Salta i post già scaricati
        if post.get("download_status") == "ok" and Path(post.get("local_img_path", "")).exists():
            logger.info(f"Media già scaricato, skip: {filename_base}")
            continue

        media_type = post.get("media_type")
        media_url = post.get("media_url")

        # Log dettagliato dello stato iniziale del post
        logger.info(
            f"Elaborazione post {idx}/{total_posts} - ID: {filename_base} "
            f"(media_type={media_type}, media_url={'presente' if media_url else 'mancante'}, "
            f"download_status={post.get('download_status', 'none')})"
        )
        logger.debug(f"Progresso: {idx}/{total_posts} ({(idx / total_posts) * 100:.1f}%) completato")

        if not media_url:
            reason = "Nessun media_url presente"
            logger.warning(f"{reason} per post {filename_base}, saltato.")
            failed.append({"media_id": filename_base, "reason": reason})
            post["download_status"] = f"failed: {reason}"
            continue

        local_img_path = client_media_dir / f"{filename_base}.jpg"
        success = False

        if media_type == "IMAGE":
            success = download_file(media_url, local_img_path)

        elif media_type == "CAROUSEL_ALBUM":
            if not media_url:
                reason = "Carosello senza media_url"
                logger.warning(f"{reason} per post {filename_base}")
                failed.append({"media_id": filename_base, "reason": reason})
                post["download_status"] = f"failed: {reason}"
                continue

            logger.info(f"Carosello: media_url trovato: {media_url}")

            # Determina se è immagine o video da media_url (tipicamente l'informazione è in media_type)
            # Consideriamo IMAGE scaricata come jpg, VIDEO o REEL scaricati come mp4 + estrazione frame
            if media_type == "CAROUSEL_ALBUM" and media_url:
                # Dato che media_type è CAROUSEL_ALBUM, per sicurezza riusiamo media_url ma controlliamo estensione semplice:
                if media_url.lower().endswith(('.jpg', '.jpeg', '.png')):
                    success = download_file(media_url, local_img_path)
                else:
                    local_video_path = client_media_dir / f"{filename_base}.mp4"
                    logger.debug(f"Download video (carosello) in corso: {local_video_path}")
                    if download_file(media_url, local_video_path):
                        success = extract_frame(local_video_path, local_img_path)
                        if success and local_video_path.exists():
                            local_video_path.unlink()
                            logger.debug(f"Video temporaneo rimosso: {local_video_path}")
                    else:
                        success = False



        elif media_type in ["VIDEO", "REEL"]:
            local_video_path = client_media_dir / f"{filename_base}.mp4"
            logger.debug(f"Download video in corso: {local_video_path}")
            if download_file(media_url, local_video_path):
                success = extract_frame(local_video_path, local_img_path)
                if success and local_video_path.exists():
                    local_video_path.unlink()
                    logger.debug(f"Video temporaneo rimosso: {local_video_path}")

        
        

        if success:
            downloaded.append(filename_base)
            old_path = post.get("local_img_path")
            new_path = str(local_img_path.relative_to(BASE_DIR))
            post["local_img_path"] = new_path
            post["download_status"] = "ok"
            logger.info(f"Updated local_img_path for post {filename_base}: from {old_path} to {new_path}")
        else:
            failed.append({"media_id": filename_base, "reason": "Download fallito"})
            post["download_status"] = "failed: Download fallito"
            logger.info(f"Download fallito per post {filename_base}")

    # Riepilogo finale
    logger.info("----- RIEPILOGO DOWNLOAD -----")
    logger.info(f"✅ Scaricati: {len(downloaded)} -> {', '.join(downloaded) if downloaded else 'Nessuno'}")

    if failed:
        logger.warning("⚠️ Non scaricati:")
        for f in failed:
            logger.warning(f"  - {f['media_id']}: {f['reason']}")
    else:
        logger.info("🎉 Nessun download fallito!")

    with open(json_output, "w", encoding='utf-8') as f:
        json.dump(posts, f, ensure_ascii=False, indent=4)

    logger.info(f"✅ JSON aggiornato salvato: {json_output}")


prepare_images = main

if __name__ == "__main__":
    from utils.token_utils import load_token

    if len(sys.argv) != 4:
        logger.error("Uso corretto: python step6_prepare_images.py <client_name> <since> <until>")
        sys.exit(1)

    client_name, since, until = sys.argv[1], sys.argv[2], sys.argv[3]
    access_token = load_token()
    main(client_name, since, until, access_token)
