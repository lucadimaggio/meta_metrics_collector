import os
import sys
import time
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timezone
from utils.api_wrapper import get as api_get
from utils.logger import get_logger, log_exceptions
from utils.token_utils import load_token
from utils.client_utils import load_client_data
from utils.save_utils import save_media_as_json


logger = get_logger(__name__)

def parse_date(value: Union[str, int]) -> datetime:
    if isinstance(value, int):
        return datetime.utcfromtimestamp(value).replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as e:
        logger.error(f"Errore parsing data {value}: {e}")
        raise

def get_insights_with_fallback(media_id: str, access_token: str) -> Dict[str, int]:
    full_metrics = "impressions,reach,saved,video_views,shares,total_interactions"
    fallback_metrics = "reach,saved,shares,total_interactions"
    max_retries = 3

    # Primo tentativo con metriche complete
    for attempt in range(1, max_retries + 1):
        try:
            logger.debug(f"Chiamata insights full metrics per media {media_id}, tentativo {attempt}")
            resp = api_get(
                f"https://graph.facebook.com/v18.0/{media_id}/insights",
                params={"metric": full_metrics, "access_token": access_token}
            )
            if "error" not in resp:
                logger.info(f"Metriche complete recuperate con successo per media {media_id}")
                return parse_insights_data(resp)
            elif resp["error"]["code"] == 100:
                logger.warning(f"Errore 100: metriche complete non supportate per media {media_id}, passo a fallback")
                break  # Esci subito dal ciclo, passa a fallback senza altri retry con metriche complete
            else:
                logger.warning(f"Errore API {resp['error']} per media {media_id}, tentativo {attempt}")
                if attempt < max_retries:
                    time.sleep(2)
                else:
                    logger.error(f"Fallito recupero metriche complete per media {media_id} dopo {max_retries} tentativi")
                    return {}
        except Exception as e:
            logger.error(f"Eccezione durante insights full per media {media_id}: {e}")
            if attempt < max_retries:
                time.sleep(2)
            else:
                logger.error(f"Fallito recupero metriche complete per media {media_id} dopo {max_retries} tentativi per eccezione")
                return {}

    # Fallback con metriche ridotte (retry opzionali, qui manteniamo 1 tentativo per semplicità)
    try:
        logger.debug(f"Chiamata insights fallback metrics per media {media_id}")
        resp = api_get(
            f"https://graph.facebook.com/v18.0/{media_id}/insights",
            params={"metric": fallback_metrics, "access_token": access_token}
        )
        if "error" not in resp:
            logger.info(f"Metriche fallback recuperate con successo per media {media_id}")
            return parse_insights_data(resp)
        else:
            logger.error(f"Errore API fallback {resp['error']} per media {media_id}")
            return {}
    except Exception as e:
        logger.error(f"Eccezione durante insights fallback per media {media_id}: {e}")
        return {}



def parse_insights_data(resp: Dict[str, Any]) -> Dict[str, int]:
    metrics = {}
    for metric in resp.get("data", []):
        name = metric.get("name")
        values = metric.get("values", [])
        if values:
            metrics[name] = values[-1].get("value", 0)
    return metrics

@log_exceptions
def get_media_list(
    ig_user_id: str,
    access_token: str,
    since: int,
    until: int,
    client_name: str,
    extra_fields: Optional[List[str]] = None
) -> List[Dict[str, Any]]:

    base_url = f"https://graph.facebook.com/v18.0/{ig_user_id}/media"
    base_fields = [
        "id", "caption", "media_type", "media_url", "permalink", "timestamp", "children", "duration"
    ]
    if extra_fields:
        fields = list(set(base_fields + extra_fields))
    else:
        fields = base_fields

    params = {
        "fields": ",".join(fields),
        "since": since,
        "until": until,
        "access_token": access_token
    }

    all_media = []
    next_url = base_url
    processed = 0

    logger.info(f"Avvio recupero media per IG user {ig_user_id}")

    since_dt = parse_date(since)
    until_dt = parse_date(until)

    while next_url:
        data = api_get(next_url, params=params if next_url == base_url else {})
        if "error" in data:
            logger.error(f"Errore API: {data['error']}")
            return []

        items = data.get("data", [])

        logger.info(f"Recuperata pagina con {len(items)} media.")

        for item in items:
            try:
                timestamp = item.get("timestamp")
                ts_obj = parse_date(timestamp)

                if not (since_dt <= ts_obj <= until_dt):
                    continue

                media_type = item.get("media_type", "")
                if media_type == "STORY":
                    # Gestisci diversamente, ad es. salta metriche o logga e continua
                    logger.info(f"Media ID {item.get('id')} è STORY, salto recupero metriche.")
                    continue

                if media_type == "CAROUSEL_ALBUM" and "children" in item:
                    children_data = item["children"].get("data", [])
                    aggregated_metrics = {
                        "impressions": 0,
                        "reach": 0,
                        "saved": 0,
                        "video_views": 0,
                        "shares": 0,
                        "total_interactions": 0,
                        "engagement": 0
                    }
                    for child in children_data:
                        child_id = child.get("id")
                        logger.debug(f"Recupero child media {child_id} di carosello")
                        success = False
                        max_retries = 3
                        for attempt in range(1, max_retries + 1):
                            child_resp = api_get(
                                f"https://graph.facebook.com/v18.0/{child_id}",
                                params={"fields": "media_url,media_type,timestamp,permalink,caption,duration,like_count,comments_count", "access_token": access_token}
                            )
                            if "error" not in child_resp:
                                child_data = child_resp
                                media_entry = {
                                    "media_id": child_data.get("id", child_id),
                                    "caption": child_data.get("caption", ""),
                                    "media_type": child_data.get("media_type", "IMAGE"),
                                    "media_url": child_data.get("media_url"),
                                    "permalink": child_data.get("permalink"),
                                    "timestamp": child_data.get("timestamp", timestamp),
                                    "duration": child_data.get("duration"),
                                    "children": [],
                                    "like_count": child_data.get("like_count", 0),
                                    "comments_count": child_data.get("comments_count", 0),
                                }

                                logger.info(f"Avvio recupero metriche per media ID {media_entry['media_id']}")
                                metrics = get_insights_with_fallback(media_entry['media_id'], access_token)

                                engagement = (
                                    media_entry.get("like_count", 0) +
                                    media_entry.get("comments_count", 0) +
                                    metrics.get("saved", 0)
                                )
                                media_entry.update({
                                    "impressions": metrics.get("impressions", 0),
                                    "reach": metrics.get("reach", 0),
                                    "saved": metrics.get("saved", 0),
                                    "video_views": metrics.get("video_views", 0),
                                    "shares": metrics.get("shares", 0),
                                    "total_interactions": metrics.get("total_interactions", 0),
                                    "engagement": engagement,
                                })
                                logger.info(f"Metriche recuperate con successo per media ID {media_entry['media_id']}")

                                # Accumula metriche per aggregazione carosello
                                for key in aggregated_metrics.keys():
                                    aggregated_metrics[key] += media_entry.get(key, 0)

                                all_media.append(media_entry)
                                processed += 1
                                logger.info(f"Media aggiunto: {media_entry['media_id']}")
                                if processed % 25 == 0:
                                    logger.info(f"Trovati {processed} media…")
                                success = True
                                break
                            else:
                                logger.warning(f"Retry {attempt} per child media {child_id}: {child_resp['error']}")
                                if attempt < max_retries:
                                    time.sleep(2)
                        if not success:
                            logger.error(f"Impossibile recuperare child media {child_id} dopo {max_retries} tentativi")

                    # Aggiungi anche un entry aggregata per il carosello se vuoi,
                    # ad es. con id dell’album e metriche sommate
                    album_entry = {
                        "media_id": item.get("id"),
                        "caption": item.get("caption", ""),
                        "media_type": media_type,
                        "media_url": item.get("media_url"),
                        "permalink": item.get("permalink"),
                        "timestamp": timestamp,
                        "duration": item.get("duration"),
                        "children": [],  # opzionale, puoi anche lasciare vuoto o lista dei figli
                    }
                    album_entry.update(aggregated_metrics)
                    all_media.append(album_entry)

                else:
                    # media singolo (non carosello, non story)
                    media_entry = {
                        "media_id": item.get("id"),
                        "caption": item.get("caption", ""),
                        "media_type": media_type,
                        "media_url": item.get("media_url"),
                        "permalink": item.get("permalink"),
                        "timestamp": timestamp,
                        "duration": item.get("duration"),
                        "children": [],
                        "like_count": item.get("like_count", 0),
                        "comments_count": item.get("comments_count", 0),
                    }

                    logger.info(f"Avvio recupero metriche per media ID {media_entry['media_id']}")
                    metrics = get_insights_with_fallback(media_entry['media_id'], access_token)

                    engagement = (
                        media_entry.get("like_count", 0) +
                        media_entry.get("comments_count", 0) +
                        metrics.get("saved", 0)
                    )
                    media_entry.update({
                        "impressions": metrics.get("impressions", 0),
                        "reach": metrics.get("reach", 0),
                        "saved": metrics.get("saved", 0),
                        "video_views": metrics.get("video_views", 0),
                        "shares": metrics.get("shares", 0),
                        "total_interactions": metrics.get("total_interactions", 0),
                        "engagement": engagement,
                    })
                    logger.info(f"Metriche recuperate con successo per media ID {media_entry['media_id']}")

                    all_media.append(media_entry)
                    processed += 1
                    logger.info(f"Media aggiunto: {media_entry['media_id']}")
                    if processed % 25 == 0:
                        logger.info(f"Trovati {processed} media…")
            except Exception as e:
                media_id = item.get("id", "unknown")
                logger.exception(f"Errore nel parsing di media_id {media_id}: {e}")

        next_url = data.get("paging", {}).get("next")
        params = {}

    logger.info(f"Totale media raccolti: {len(all_media)}")
    # Converti i timestamp in stringhe data per il salvataggio JSON
    since_str = datetime.utcfromtimestamp(since).strftime("%Y-%m-%d")
    until_str = datetime.utcfromtimestamp(until).strftime("%Y-%m-%d")

    # Salva JSON raw dei media
    save_media_as_json(all_media, client_name, since_str, until_str)
    logger.info(f"File JSON raw_media salvato per {client_name} da {since_str} a {until_str}")

    return all_media

@log_exceptions
def run(client_name: str, since_unix: int, until_unix: int) -> List[Dict[str, Any]]:
    logger.info(f"Step 3 avviato per {client_name}")

    token = load_token()
    client_data = load_client_data(client_name)
    ig_user_id = client_data.get("ig_user_id")

    if not token or not ig_user_id:
        logger.error(f"Impossibile trovare token o ig_user_id per cliente {client_name}")
        return []

    media_list = get_media_list(ig_user_id, token, since_unix, until_unix, client_name)
    logger.info(f"Step 3 completato: {len(media_list)} media recuperati.")
    return media_list

if __name__ == "__main__":
    if len(sys.argv) != 4:
        logger.error("Uso: python step3_get_media.py <client_name> <since_unix> <until_unix>")
        sys.exit(1)

    client_name = sys.argv[1]
    try:
        since_unix = int(sys.argv[2])
        until_unix = int(sys.argv[3])
    except ValueError:
        logger.error("I parametri 'since_unix' e 'until_unix' devono essere timestamp interi.")
        sys.exit(1)

    run(client_name, since_unix, until_unix)
