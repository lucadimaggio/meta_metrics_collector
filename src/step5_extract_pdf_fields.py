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
    input_csv_path = os.path.join("output", client_name, f"content_report_{since}_{until}.csv")
    output_json_path = os.path.join("output", client_name, f"pdf_fields_{since}_{until}_with_images.json")

    logger.info(f"Verifico esistenza file CSV: {input_csv_path}")
    if not os.path.exists(input_csv_path):
        logger.error(f"File CSV non trovato: {input_csv_path}")
        logger.error("Assicurati che il file CSV venga generato correttamente dopo lo step 4 (analisi contenuti).")
        return

    with open(input_csv_path, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        posts = []
        for row in reader:
            try:
                post = {
                    "id": row.get("id", ""),
                    "timestamp": row.get("timestamp", ""),
                    "permalink": row.get("permalink", ""),
                    "quality_score": safe_float(row.get("quality_score", 0)),
                    "media_type": row.get("media_type", ""),
                    "media_url": row.get("media_url", ""),
                    "caption": row.get("caption", ""),
                    "impressions": safe_int(row.get("impressions", 0)),
                    "reach": safe_int(row.get("reach", 0)),
                    "saved": safe_int(row.get("saved", 0)),
                    "video_views": safe_int(row.get("video_views", 0)),
                    "like_count": safe_int(row.get("like_count", 0)),
                    "comments_count": safe_int(row.get("comments_count", 0)),
                    "engagement_rate": safe_float(row.get("engagement_rate", 0.0)),
                }
                posts.append(post)
            except Exception as e:
                logger.warning(f"Errore creando post da riga CSV: {e}")


    if not posts:
        logger.warning("Nessun post valido trovato nel CSV.")
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
        try:
            date_formatted = datetime.fromisoformat(post['timestamp']).strftime('%Y-%m-%d')
        except ValueError:
            logger.warning(f"Timestamp non valido per post ID {post['id']}: {post['timestamp']}, uso valore originale.")
            date_formatted = post['timestamp']

        image_local_path = os.path.join("media", client_name, f"post_{idx}.jpg")
        logger.info(f"Assigning local_img_path for post {idx}: {image_local_path}")

        post_data = {
            "id": post["id"],
            "timestamp": date_formatted,
            "permalink": post["permalink"],
            "media_type": post["media_type"],
            "media_url": post["media_url"],  # URL remoto mantenuto
            "local_img_path": image_local_path,  # Percorso locale aggiunto
            "quality_score": post["quality_score"],
            "caption": post["caption"][:100],  # Caption sintetica, max 100 caratteri
            # Nuove metriche aggiuntive
            "impressions": post["impressions"],
            "reach": post["reach"],
            "saved": post["saved"],
            "video_views": post["video_views"],
            "like_count": post["like_count"],
            "comments_count": post["comments_count"],
            "engagement_rate": post["engagement_rate"],
        }
        logger.info(f"Post {idx} data: {post_data}")

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
