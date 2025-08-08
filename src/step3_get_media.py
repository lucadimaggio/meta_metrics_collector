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
                f"https://graph.facebook.com/v23.0/{media_id}/insights",
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
            f"https://graph.facebook.com/v23.0/{media_id}/insights",
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
def get_media_complete_data(
    
    ig_user_id: str,
    
    access_token: str,
    since: int,
    until: int,
    client_name: str,
) -> List[Dict[str, Any]]:
    
    print(f"[DEBUG] Input parameters:")
    print(f"  ig_user_id: {ig_user_id}")
    print(f"  access_token: {'<hidden>'}")  # non stampare il token reale per sicurezza
    print(f"  since (timestamp): {since}")
    print(f"  until (timestamp): {until}")
    print(f"  client_name: {client_name}")

    """
    Flusso completo:
    1) Recupera lista media (id + media_type)
    2) Per ogni media, chiama API dati dettagliati + insights a seconda del tipo
    3) Aggrega dati per caroselli
    4) Salva JSON raw
    """

    # 1. Recupera lista media con id e media_type
    media_list_url = f"https://graph.facebook.com/v23.0/{ig_user_id}/media"
    media_list_params = {
        "fields": "id,media_type",
        "since": since,
        "until": until,
        "access_token": access_token
}

    all_media = []
    next_url = media_list_url
    processed = 0

    logger.info(f"Recupero lista media ID + tipo per IG user {ig_user_id}")

    while next_url:
        data = api_get(next_url, params=media_list_params if next_url == media_list_url else {})
        if "error" in data:
            logger.error(f"Errore API recupero lista media: {data['error']}")
            return []

        items = data.get("data", [])
        logger.info(f"Recuperata pagina con {len(items)} media.")

        for item in items:
            media_id = item.get("id")
            media_type = item.get("media_type")

            try:
                logger.info(f"Processo media ID {media_id} di tipo {media_type}")

                # 2. Dati dettagliati e insights a seconda del tipo
                if media_type == "CAROUSEL_ALBUM":
                    # Dati dettagliati carosello
                    fields = "id,media_type,caption,like_count,comments_count,timestamp,children{id,media_type,media_url,thumbnail_url,timestamp,permalink}"
                    details_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}",
                        params={"fields": fields, "access_token": access_token}
                    )

                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli carosello {media_id}: {details_resp['error']}")
                        continue

                    # Insights carosello
                    metrics_list = "comments,follows,likes,profile_activity,profile_visits,reach,saved,shares,total_interactions"
                    insights_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}/insights",
                        params={"metric": metrics_list, "access_token": access_token}
                    )

                    if "error" in insights_resp:
                        logger.error(f"Errore API insights carosello {media_id}: {insights_resp['error']}")
                        insights_data = {}
                    else:
                        insights_data = parse_insights_data(insights_resp)

                    # Aggrega dati figli
                    children = details_resp.get("children", {}).get("data", [])
                    children_data = []
                    for child in children:
                        # Per ogni child prendi i campi già presenti
                        children_data.append({
                            "id": child.get("id"),
                            "media_type": child.get("media_type"),
                            "media_url": child.get("media_url"),
                            "thumbnail_url": child.get("thumbnail_url"),
                            "timestamp": child.get("timestamp"),
                            "permalink": child.get("permalink"),
                        })

                    media_entry = {
                        "media_id": media_id,
                        "media_type": media_type,
                        "caption": details_resp.get("caption", ""),
                        "like_count": details_resp.get("like_count", 0),
                        "comments_count": details_resp.get("comments_count", 0),
                        "timestamp": details_resp.get("timestamp"),
                        "children": children_data,
                        **insights_data
                    }

                elif media_type == "IMAGE":
                    # Dati dettagliati foto
                    fields = "id,media_type,media_url,timestamp,caption,like_count,comments_count,permalink"
                    details_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}",
                        params={"fields": fields, "access_token": access_token}
                    )
                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli foto {media_id}: {details_resp['error']}")
                        continue

                    # Insights foto
                    metrics_list = "comments,follows,likes,profile_activity,profile_visits,reach,saved,shares,total_interactions"
                    insights_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}/insights",
                        params={"metric": metrics_list, "access_token": access_token}
                    )

                    if "error" in insights_resp:
                        logger.error(f"Errore API insights foto {media_id}: {insights_resp['error']}")
                        insights_data = {}
                    else:
                        insights_data = parse_insights_data(insights_resp)

                    media_entry = {
                        "media_id": media_id,
                        "media_type": media_type,
                        "media_url": details_resp.get("media_url"),
                        "caption": details_resp.get("caption", ""),
                        "like_count": details_resp.get("like_count", 0),
                        "comments_count": details_resp.get("comments_count", 0),
                        "timestamp": details_resp.get("timestamp"),
                        "permalink": details_resp.get("permalink"),
                        **insights_data
                    }

                elif media_type in ("VIDEO", "REEL"):
                    # Dati dettagliati video/reel
                    fields = ("id,media_type,media_url,thumbnail_url,timestamp,caption,"
                              "like_count,comments_count,permalink,comments{from,like_count,media,text}")
                    details_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}",
                        params={"fields": fields, "access_token": access_token}
                    )
                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli video/reel {media_id}: {details_resp['error']}")
                        continue

                    # Insights video/reel
                    metrics_list = ("comments,likes,reach,saved,shares,total_interactions,views,"
                                    "ig_reels_avg_watch_time,ig_reels_video_view_total_time")
                    insights_resp = api_get(
                        f"https://graph.facebook.com/v23.0/{media_id}/insights",
                        params={"metric": metrics_list, "access_token": access_token}
                    )

                    if "error" in insights_resp:
                        logger.error(f"Errore API insights video/reel {media_id}: {insights_resp['error']}")
                        insights_data = {}
                    else:
                        insights_data = parse_insights_data(insights_resp)

                    media_entry = {
                        "media_id": media_id,
                        "media_type": media_type,
                        "media_url": details_resp.get("media_url"),
                        "thumbnail_url": details_resp.get("thumbnail_url"),
                        "caption": details_resp.get("caption", ""),
                        "like_count": details_resp.get("like_count", 0),
                        "comments_count": details_resp.get("comments_count", 0),
                        "timestamp": details_resp.get("timestamp"),
                        "permalink": details_resp.get("permalink"),
                        "comments": details_resp.get("comments", []),
                        **insights_data
                    }

                else:
                    logger.warning(f"Tipo media sconosciuto o non gestito: {media_type} per media {media_id}")
                    continue

                all_media.append(media_entry)
                processed += 1
                logger.info(f"Media processato e aggiunto: {media_id} ({media_type})")
                if processed % 25 == 0:
                    logger.info(f"{processed} media processati...")

            except Exception as e:
                logger.exception(f"Errore processing media {media_id}: {e}")

        next_url = data.get("paging", {}).get("next")
        media_list_params = {}

    logger.info(f"Totale media processati: {len(all_media)}")
    if len(all_media) > 0:
        logger.info(f"[DEBUG] Esempio primo media processato:\n{all_media[0]}")
    else:
        logger.info("[DEBUG] Nessun media processato.")

    # Salvataggio JSON raw completo
    since_str = datetime.utcfromtimestamp(since).strftime("%Y-%m-%d")
    until_str = datetime.utcfromtimestamp(until).strftime("%Y-%m-%d")
    save_media_as_json(all_media, client_name, since_str, until_str)
    logger.info(f"File JSON raw_media salvato per {client_name} da {since_str} a {until_str}")
    

    return all_media


@log_exceptions
def run(client_name: str, since_unix: int, until_unix: int) -> List[Dict[str, Any]]:
    print(f"[DEBUG] run() chiamato con parametri:")
    print(f"  client_name: {client_name}")
    print(f"  since_unix: {since_unix}")
    print(f"  until_unix: {until_unix}")

    logger.info(f"Step 3 avviato per {client_name}")

    token = load_token()
    client_data = load_client_data(client_name)
    ig_user_id = client_data.get("ig_user_id")

    if not token or not ig_user_id:
        logger.error(f"Impossibile trovare token o ig_user_id per cliente {client_name}")
        return []

    media_list = get_media_complete_data(ig_user_id, token, since_unix, until_unix, client_name)
    logger.info(f"Step 3 completato: {len(media_list)} media recuperati.")
    logger.info(f"[DEBUG] Numero media recuperati da get_media_complete_data: {len(media_list)}")

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