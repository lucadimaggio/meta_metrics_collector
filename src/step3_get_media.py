import os
import sys
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timezone
from utils.api_wrapper import get as api_get
from utils.logger import get_logger, log_exceptions
from utils.token_utils import load_token
from utils.client_utils import load_client_data

logger = get_logger(__name__)

def parse_date(value: Union[str, int]) -> datetime:
    if isinstance(value, int):
        return datetime.utcfromtimestamp(value).replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as e:
        logger.error(f"Errore parsing data {value}: {e}")
        raise

@log_exceptions
def get_media_list(
    ig_user_id: str,
    access_token: str,
    since: Union[str, int],
    until: Union[str, int],
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

        for item in items:
            try:
                timestamp = item.get("timestamp")
                ts_obj = parse_date(timestamp)

                if not (since_dt <= ts_obj <= until_dt):
                    continue

                if item.get("media_type") == "CAROUSEL_ALBUM" and "children" in item:
                    children_data = item["children"].get("data", [])
                    for child in children_data:
                        child_id = child.get("id")
                        logger.debug(f"Recupero child media {child_id} di carosello")
                        success = False
                        max_retries = 3
                        for attempt in range(1, max_retries + 1):
                            child_resp = api_get(
                                f"https://graph.facebook.com/v18.0/{child_id}",
                                params={"fields": "media_url,media_type,timestamp,permalink,caption,duration", "access_token": access_token}
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
                                    "children": []
                                }
                                all_media.append(media_entry)
                                processed += 1
                                logger.info(f"Media aggiunto: {media_entry['media_id']}")
                                if processed % 25 == 0:
                                    logger.info(f"Trovati {processed} media…")
                                success = True
                                break
                            else:
                                logger.warning(f"Retry {attempt} per child media {child_id}: {child_resp['error']}")
                        if not success:
                            logger.error(f"Impossibile recuperare child media {child_id} dopo {max_retries} tentativi")
                else:
                    media_entry = {
                        "media_id": item.get("id"),
                        "caption": item.get("caption", ""),
                        "media_type": item.get("media_type"),
                        "media_url": item.get("media_url"),
                        "permalink": item.get("permalink"),
                        "timestamp": timestamp,
                        "duration": item.get("duration"),
                        "children": []
                    }
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
    return all_media

@log_exceptions
def run(client_name: str, since: Union[str, int], until: Union[str, int]) -> List[Dict[str, Any]]:
    logger.info(f"Step 3 avviato per {client_name}")

    token = load_token()
    client_data = load_client_data(client_name)
    ig_user_id = client_data.get("ig_user_id")

    if not token or not ig_user_id:
        logger.error(f"Impossibile trovare token o ig_user_id per cliente {client_name}")
        return []

    media_list = get_media_list(ig_user_id, token, since, until)
    logger.info(f"Step 3 completato: {len(media_list)} media recuperati.")
    return media_list

if __name__ == "__main__":
    if len(sys.argv) != 4:
        logger.error("Uso: python step3_get_media.py <client_name> <since> <until>")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]

    run(client_name, since, until)
