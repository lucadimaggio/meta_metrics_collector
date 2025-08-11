import os
import sys
import time
from typing import List, Dict, Any, Union, Optional
from datetime import datetime, timezone, timedelta
from utils.api_wrapper import get as api_get
from utils.logger import get_logger, log_exceptions
from utils.token_utils import load_token
from utils.client_utils import load_client_data
from utils.save_utils import save_media_as_json


logger = get_logger(__name__)


def generate_monthly_intervals(start_date: datetime, end_date: datetime) -> List[Dict[str, datetime]]:
    intervals = []
    current_start = start_date

    while current_start <= end_date:
        # Calcola il primo giorno del mese successivo
        if current_start.month == 12:
            next_month_start = datetime(year=current_start.year + 1, month=1, day=1)
        else:
            next_month_start = datetime(year=current_start.year, month=current_start.month + 1, day=1)

        current_end = next_month_start - timedelta(seconds=1)
        if current_end > end_date:
            current_end = end_date

        intervals.append({"since": current_start, "until": current_end})
        current_start = current_end + timedelta(seconds=1)

    return intervals


def parse_date(value: Union[str, int]) -> datetime:
    if isinstance(value, int):
        return datetime.utcfromtimestamp(value).replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception as e:
        logger.error(f"Errore parsing data {value}: {e}")
        raise

def get_insights_with_fallback(media_id: str, access_token: str) -> Dict[str, int]:
    full_metrics = "reach,saved,video_views,shares,total_interactions"
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
    
    logger.info(f"[DEBUG] Input parameters:")
    logger.info(f"  ig_user_id: {ig_user_id}")
    logger.info(f"  access_token: {'<hidden>'}")  # non stampare il token reale per sicurezza
    logger.info(f"  since (timestamp): {since}")
    logger.info(f"  until (timestamp): {until}")
    logger.info(f"  client_name: {client_name}")

    """
    Flusso completo:
    1) Recupera lista media (id + media_type) suddividendo in intervalli mensili se > 1 mese
    2) Per ogni media, chiama API dati dettagliati + insights a seconda del tipo
    3) Aggrega dati per caroselli
    4) Salva JSON raw finale unito
    """

    start_date = datetime.utcfromtimestamp(since).replace(tzinfo=None)
    end_date = datetime.utcfromtimestamp(until).replace(tzinfo=None)
    total_days = (end_date - start_date).days

    logger.info(f"Inizio recupero media per {client_name} da {start_date.strftime('%Y-%m-%d')} a {end_date.strftime('%Y-%m-%d')}")
    
    if total_days > 31:
        intervals = generate_monthly_intervals(start_date, end_date)
        logger.info(f"Intervallo > 1 mese, suddiviso in {len(intervals)} intervalli mensili")
    else:
        intervals = [{"since": start_date, "until": end_date}]

    all_media_complete = []
    processed_media_count = 0

    for interval in intervals:
        since_ts = int(interval["since"].replace(tzinfo=timezone.utc).timestamp())
        until_ts = int(interval["until"].replace(tzinfo=timezone.utc).timestamp())
        logger.info(f"Recupero media da {interval['since'].strftime('%Y-%m-%d')} a {interval['until'].strftime('%Y-%m-%d')}")

        media_list_url = f"https://graph.facebook.com/v23.0/{ig_user_id}/media"
        media_list_params = {
            "fields": "id,media_type",
            "since": since_ts,
            "until": until_ts,
            "access_token": access_token
        }

        next_url = media_list_url
        media_list_interval = []

        # Pagina media base per intervallo mensile
        while next_url:
            data = api_get(next_url, params=media_list_params if next_url == media_list_url else {})
            if "error" in data:
                logger.error(f"Errore API recupero lista media per intervallo {interval['since'].strftime('%Y-%m-%d')} - {interval['until'].strftime('%Y-%m-%d')}: {data['error']}")
                break

            items = data.get("data", [])
            media_list_interval.extend(items)
            logger.debug(f"Recuperati {len(items)} media in pagina corrente dell'intervallo {interval['since'].strftime('%Y-%m-%d')} - {interval['until'].strftime('%Y-%m-%d')}")

            next_url = data.get("paging", {}).get("next")
            media_list_params = {}

        logger.info(f"Totale media recuperati nell'intervallo {interval['since'].strftime('%Y-%m-%d')} - {interval['until'].strftime('%Y-%m-%d')}: {len(media_list_interval)}")

        # Per ogni media, recupera dettagli e insights completi
        for item in media_list_interval:
            media_id = item.get("id")
            media_type = item.get("media_type")

            try:
                logger.info(f"Processo media ID {media_id} di tipo {media_type}")

                if media_type == "CAROUSEL_ALBUM":
                    fields = "id,media_type,caption,like_count,comments_count,timestamp,children{id,media_type,media_url,thumbnail_url,timestamp,permalink}"
                    details_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}",
                                           params={"fields": fields, "access_token": access_token})
                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli carosello {media_id}: {details_resp['error']}")
                        continue

                    metrics_list = "comments,follows,likes,profile_activity,profile_visits,reach,saved,shares,total_interactions"
                    insights_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}/insights",
                                            params={"metric": metrics_list, "access_token": access_token})
                    if "error" in insights_resp:
                        logger.error(f"Errore API insights carosello {media_id}: {insights_resp['error']}")
                        insights_data = {}
                    else:
                        insights_data = parse_insights_data(insights_resp)

                    children = details_resp.get("children", {}).get("data", [])
                    children_data = []
                    for child in children:
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
                    fields = "id,media_type,media_url,timestamp,caption,like_count,comments_count,permalink"
                    details_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}",
                                           params={"fields": fields, "access_token": access_token})
                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli foto {media_id}: {details_resp['error']}")
                        continue

                    metrics_list = "comments,follows,likes,profile_activity,profile_visits,reach,saved,shares,total_interactions"
                    insights_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}/insights",
                                            params={"metric": metrics_list, "access_token": access_token})
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
                    fields = ("id,media_type,media_url,thumbnail_url,timestamp,caption,"
                              "like_count,comments_count,permalink,comments{from,like_count,media,text}")
                    details_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}",
                                           params={"fields": fields, "access_token": access_token})
                    if "error" in details_resp:
                        logger.error(f"Errore API dettagli video/reel {media_id}: {details_resp['error']}")
                        continue

                    metrics_list = ("comments,likes,reach,saved,shares,total_interactions,views,"
                                    "ig_reels_avg_watch_time,ig_reels_video_view_total_time")
                    insights_resp = api_get(f"https://graph.facebook.com/v23.0/{media_id}/insights",
                                            params={"metric": metrics_list, "access_token": access_token})
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

                all_media_complete.append(media_entry)
                processed_media_count += 1
                if processed_media_count % 25 == 0:
                    logger.info(f"{processed_media_count} media processati finora...")

            except Exception as e:
                logger.exception(f"Errore processing media {media_id}: {e}")

    logger.info(f"Totale media processati in tutti gli intervalli: {processed_media_count}")

    since_str = start_date.strftime("%Y-%m-%d")
    until_str = end_date.strftime("%Y-%m-%d")
    save_media_as_json(all_media_complete, client_name, since_str, until_str)
    logger.info(f"File JSON raw_media salvato per {client_name} da {since_str} a {until_str}")

    return all_media_complete

from typing import List, Dict

def run_step3(config: dict) -> List[Dict]:
    client_name = config.get("client_name")
    since_unix = config.get("since_unix")
    until_unix = config.get("until_unix")
    access_token = config.get("access_token")
    ig_user_id = config.get("ig_user_id")

    logger.info(f"run_step3 avviato per cliente {client_name}")

    # Verifica presenza parametri essenziali
    if not all([client_name, since_unix, until_unix, access_token, ig_user_id]):
        logger.error("Parametri mancanti nel config per run_step3")
        return []

    try:
        media_list = get_media_complete_data(
            ig_user_id=ig_user_id,
            access_token=access_token,
            since=since_unix,
            until=until_unix,
            client_name=client_name
        )
        logger.info(f"run_step3 completato: {len(media_list)} media recuperati per cliente {client_name}")
        return media_list

    except Exception as e:
        logger.exception(f"Errore in run_step3 per cliente {client_name}: {e}")
        return []



@log_exceptions
def run(client_name: str, since_unix: int, until_unix: int) -> List[Dict[str, Any]]:
    logger.info(f"[DEBUG] run() chiamato con parametri:")
    logger.info(f"  client_name: {client_name}")
    logger.info(f"  since_unix: {since_unix}")
    logger.info(f"  until_unix: {until_unix}")

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