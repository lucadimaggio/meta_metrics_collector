import csv
import json
import os
import sys
from datetime import datetime
from utils.logger import get_logger, log_exceptions

logger = get_logger(__name__)

def safe_int(val):
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

def safe_float(val):
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0



@log_exceptions
def extract_top_posts(client_name: str, since: str, until: str, top_n: int = 3):
    input_json_path = os.path.join("media", client_name, f"raw_media_{since}_{until}.json")
    output_json_path = os.path.join("output", client_name, f"pdf_fields_{since}_{until}_with_images.json")

    logger.info(f"Verifico esistenza file JSON raw_media: {input_json_path}")
    if not os.path.exists(input_json_path):
        logger.error(f"File JSON raw_media non trovato: {input_json_path}")
        logger.error("Assicurati che il file JSON raw_media venga generato correttamente dallo step precedente.")
        return

    with open(input_json_path, 'r', encoding="utf-8") as jsonfile:
        try:
            raw_data = json.load(jsonfile)
            entry_by_media_id = {e.get("media_id"): e for e in raw_data}

            logger.info(f"Caricati {len(raw_data)} post dal file JSON raw_media")
        except Exception as e:
            logger.error(f"Errore nel parsing del file JSON: {e}")
            return

    posts = []
    for entry in raw_data:
        try:
            post = {
                "media_id": entry.get("media_id", ""),
                "timestamp": entry.get("timestamp", ""),
                "permalink": entry.get("permalink", ""),
                "quality_score": safe_float(entry.get("quality_score", 0)),
                "media_type": entry.get("media_type", ""),
                "media_url": entry.get("media_url", ""),
                "caption": entry.get("caption", ""),
                "reach": safe_int(entry.get("reach", 0)),
                "saved": safe_int(entry.get("saved", 0)),
                "views": safe_int(entry.get("views", 0)),
                "like_count": safe_int(entry.get("like_count", 0)),
                "comments_count": safe_int(entry.get("comments_count", 0)),
                "total_interactions": safe_float(entry.get("total_interactions", 0.0)),
            }
            logger.info(f"[RAW INPUT] Post media_id={post['media_id']}: {post}")
            posts.append(post)
        except Exception as e:
            logger.warning(f"Errore creando post da JSON raw_media: {e}")



    if not posts:
        logger.warning("Nessun post valido trovato nel file JSON raw_media.")

        return

    # Mostra campi individuati per conferma
    campi_disponibili = list(posts[0].keys())
    logger.info(f"Campi trovati nei dati: {', '.join(campi_disponibili)}")

    # Log dettagli dei primi post per anteprima
    max_show = 5
    logger.info(f"Esempio dati dei primi {max_show} post:")
    for i, post in enumerate(posts[:max_show], 1):
        logger.info(f"Post {i}: id={post.get('id')}, timestamp={post.get('timestamp')}, permalink={post.get('permalink')}, media_type={post.get('media_type')}")

    prompt = "Vuoi proseguire con questi campi? (s = sì, n = no): "
    logger.info(prompt)
    risposta = input(prompt).strip().lower()
    if risposta != 's':
        logger.info("Processo interrotto dall'utente.")
        sys.exit(0)
    else:
        logger.info("Continuo con l'estrazione top post...")

    # Ordina post per quality_score decrescente
    sorted_posts = sorted(posts, key=lambda x: x['quality_score'], reverse=True)

    # Seleziona i primi top_n post
    top_posts = sorted_posts[:top_n]

    # Prepara dati per JSON
    top_posts_data = []
    for idx, post in enumerate(top_posts, 1):
        entry = entry_by_media_id.get(post["media_id"], {})

        try:
            date_formatted = datetime.fromisoformat(post['timestamp']).strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Timestamp non valido per post media_id {post['media_id']}: {post['timestamp']}, uso valore originale.")
            date_formatted = post['timestamp']

        image_local_path = os.path.join("media", client_name, f"post_{idx}.jpg")
        logger.info(f"Assigning local_img_path for post {idx}: {image_local_path}")

        media_url = post["media_url"]  # default preso dal post

        if post["media_type"] == "CAROUSEL_ALBUM":
            children = entry.get("children", [])
            logger.info(f"Post {idx} è un carosello con {len(children)} children, cerco primo media_url valido...")
            first_media_url = None
            for child in children:
                url = child.get("media_url")
                if url:
                    first_media_url = url
                    break
            if first_media_url:
                logger.info(f"Post {idx} - Primo media_url valido dal carosello trovato: {first_media_url}")
                media_url = first_media_url
            else:
                logger.info(f"Post {idx} - Nessun media_url valido trovato nei children, uso media_url originale.")

        post_data = {
            "media_id": post["media_id"],
            "timestamp": date_formatted,
            "permalink": post["permalink"],
            "media_type": post["media_type"],
            "media_url": media_url,
            "local_img_path": image_local_path,
            "quality_score": post["quality_score"],
            "caption": post["caption"][:100],
            "reach": post["reach"],
            "saved": post["saved"],
            "views": post["views"],
            "like_count": post["like_count"],
            "comments_count": post["comments_count"],
            "total_interactions": post["total_interactions"],
        }

        if post["media_type"] == "CAROUSEL_ALBUM":
            post_data["shares"] = entry.get("shares", 0)
            post_data["total_interactions"] = entry.get("total_interactions", 0)

        if post["media_type"].upper() == "VIDEO":
            post_data["shares"] = entry.get("shares", None)
            post_data["total_interactions"] = entry.get("total_interactions", None)
            post_data["ig_reels_avg_watch_time"] = entry.get("ig_reels_avg_watch_time", None)
            post_data["ig_reels_video_view_total_time"] = entry.get("ig_reels_video_view_total_time", None)

        logger.info(f"[PDF FIELDS OUTPUT] Post {idx}: {post_data}")

        top_posts_data.append(post_data)

    # Salva i dati in formato JSON solo nel file con suffisso _with_images.json
    os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
    with open(output_json_path, 'w', encoding='utf-8') as json_file:
        json.dump(top_posts_data, json_file, ensure_ascii=False, indent=2)

    logger.info(f"Top {len(top_posts_data)} post salvati correttamente in {output_json_path}")


@log_exceptions
def main():
    if len(sys.argv) < 4:
        logger.error("Uso: python step5_extract_top_posts.py <client_name> <since> <until>")
        sys.exit(1)
    else:
        client_name = sys.argv[1]
        since = sys.argv[2]
        until = sys.argv[3]
        extract_top_posts(client_name, since, until)


if __name__ == "__main__":
    main()