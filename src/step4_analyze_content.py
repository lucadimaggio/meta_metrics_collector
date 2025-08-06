import os
import json
import re
import argparse
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import Counter
import csv
import logging

logger = logging.getLogger(__name__)

OUTPUT_DIR = "output"
MEDIA_DIR = "media"

CTA_KEYWORDS = ["clicca", "scopri", "link in bio", "visita", "acquista", "ordina"]
TONE_KEYWORDS = {
    "promozionale": ["sconto", "promo", "acquista", "offerta", "spedizione gratuita"],
    "educativo": ["sapevi", "curiosità", "consiglio", "perché", "come fare"],
    "ironico": ["lol", "ahah", "non è vero", "immagina se"],
    "descrittivo": ["realizzato con", "caratterizzato da", "fatto a mano"]
}

def detect_cta(caption: str) -> bool:
    return any(kw in caption.lower() for kw in CTA_KEYWORDS)

def detect_tone(caption: str) -> str:
    caption_lower = caption.lower()
    for tone, keywords in TONE_KEYWORDS.items():
        if any(kw in caption_lower for kw in keywords):
            return tone
    return "neutro"

def analyze_media(media: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []
    for m in media:
        caption = m.get("caption", "")
        timestamp = m.get("timestamp", "")
        caption_length = len(caption)
        num_hashtags = len(re.findall(r"#\w+", caption))

        result = {
            "id": m.get("id"),
            "caption": caption,
            "media_type": m.get("media_type", "unknown"),
            "media_url": m.get("media_url", ""),
            "permalink": m.get("permalink", ""),
            "caption_length": caption_length,
            "has_cta": detect_cta(caption),
            "tone": detect_tone(caption),
            "hashtag_count": num_hashtags,
            "timestamp": timestamp[:10] if timestamp else "",
        }

        score = 0
        if result["has_cta"]:
            score += 1
        if result["caption_length"] > 100:
            score += 1
        if result["hashtag_count"] >= 3:
            score += 1
        result["quality_score"] = score

        results.append(result)
    return results

def count_media_types(media_list: List[Dict]) -> Dict[str, int]:
    logger.info("Inizio conteggio dei tipi di media.")
    counts = {}
    try:
        for media in media_list:
            media_type = media.get("media_type", None)
            if not media_type:
                media_type = "UNKNOWN"
            counts[media_type] = counts.get(media_type, 0) + 1
        logger.info(f"Conteggio tipi di media completato: {counts}")
    except Exception as e:
        logger.error(f"Errore durante il conteggio dei tipi di media: {e}", exc_info=True)
    return counts

def generate_date_range(since: str, until: str) -> List[datetime]:
    start_date = datetime.strptime(since, "%Y-%m-%d").date()
    end_date = datetime.strptime(until, "%Y-%m-%d").date()
    delta = end_date - start_date
    date_list = [start_date + timedelta(days=i) for i in range(delta.days + 1)]
    logger.info(f"Generata lista date da {since} a {until}, totale {len(date_list)} giorni.")
    return date_list

def analyze_publication_frequency(media_list: List[Dict], since: str, until: str) -> Dict[str, Any]:
    logger.info("Inizio analisi frequenza e costanza pubblicazioni.")
    try:
        dates = []
        for media in media_list:
            ts = media.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.strptime(ts[:10], "%Y-%m-%d").date()
                    dates.append(dt)
                except Exception as e:
                    logger.warning(f"Formato timestamp errato '{ts}': {e}")
            else:
                logger.warning("Media senza timestamp trovato.")

        logger.info(f"Estrazioni date completate, totali: {len(dates)}")
        full_dates = generate_date_range(since, until)
        count_per_day = Counter(dates)
        logger.info(f"Conteggio contenuti per giorno calcolato.")

        active_days = [d for d in full_dates if count_per_day.get(d, 0) > 0]
        pause_days = [d for d in full_dates if count_per_day.get(d, 0) == 0]

        max_count = max(count_per_day.values()) if count_per_day else 0
        peak_days = [d for d, c in count_per_day.items() if c == max_count] if max_count > 0 else []

        detailed_report = []
        for day in full_dates:
            cnt = count_per_day.get(day, 0)
            peak_flag = cnt == max_count and cnt > 0
            detailed_report.append({
                "date": day.isoformat(),
                "content_count": cnt,
                "is_peak": peak_flag
            })

        stats = {
            "total_days": len(full_dates),
            "active_days_count": len(active_days),
            "pause_days_count": len(pause_days),
            "peak_days": [d.isoformat() for d in peak_days],
            "max_content_count": max_count,
        }

        logger.info(f"Analisi frequenza completata: {stats}")

        report_text = (
            f"Analisi pubblicazioni dal {since} al {until}:\n"
            f"Totale giorni: {stats['total_days']}\n"
            f"Giorni attivi: {stats['active_days_count']}\n"
            f"Giorni di pausa: {stats['pause_days_count']}\n"
            f"Giorni con picco di pubblicazione ({max_count} contenuti): "
            f"{', '.join(stats['peak_days']) if stats['peak_days'] else 'Nessuno'}\n"
        )

        return {
            "stats": stats,
            "detailed_report": detailed_report,
            "report_text": report_text
        }

    except Exception as e:
        logger.error(f"Errore durante analisi frequenza pubblicazioni: {e}", exc_info=True)
        return {
            "stats": {},
            "detailed_report": [],
            "report_text": "Errore durante analisi frequenza pubblicazioni."
        }

def run_analysis(client_name: str, since: str, until: str) -> None:
    file_path = os.path.join(MEDIA_DIR, client_name, f"raw_media_{since}_{until}.json")
    if not os.path.exists(file_path):
        print(f"[❌] File non trovato: {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        media = json.load(f)

    if not media:
        print(f"[⚠️] Nessun contenuto da analizzare per {client_name}.")
        return

    results = analyze_media(media)
    save_json(results, client_name, since, until)
    save_csv(results, client_name, since, until)

    media_counts = count_media_types(media)
    logger.info(f"Conteggio media types per cliente {client_name} da {since} a {until}: {media_counts}")

    frequency_analysis = analyze_publication_frequency(media, since, until)
    logger.info(f"Report frequenza pubblicazioni:\n{frequency_analysis['report_text']}")

    # Salva report testuale su file
    report_folder = os.path.join(OUTPUT_DIR, client_name)
    os.makedirs(report_folder, exist_ok=True)
    report_path = os.path.join(report_folder, f"publication_frequency_report_{since}_{until}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(frequency_analysis["report_text"])

    print(f"[✅] Analisi completata per {client_name}. Report salvato.")

def save_json(data: List[Dict[str, Any]], client_name: str, since: str, until: str):
    folder = os.path.join(OUTPUT_DIR, client_name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"content_report_{since}_{until}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_csv(data: List[Dict[str, Any]], client_name: str, since: str, until: str):
    folder = os.path.join(OUTPUT_DIR, client_name)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"content_report_{since}_{until}.csv")
    if data:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("client_name", type=str, help="Nome del cliente")
    parser.add_argument("since", type=str, help="Data iniziale (YYYY-MM-DD)")
    parser.add_argument("until", type=str, help="Data finale (YYYY-MM-DD)")
    args = parser.parse_args()

    run_analysis(args.client_name, args.since, args.until)

if __name__ == "__main__":
    main()
