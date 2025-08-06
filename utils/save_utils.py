import os
import json
import csv
from typing import List, Dict, Any

def save_media_as_json(all_media: List[Dict[str, Any]], client_name: str, since: str, until: str) -> None:
    try:
        folder_path = os.path.join("media", client_name)
        os.makedirs(folder_path, exist_ok=True)

        filename = f"raw_media_{since}_{until}.json"
        file_path = os.path.join(folder_path, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(all_media, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"[❌] Errore durante il salvataggio JSON per {client_name}: {e}")


def save_media_as_csv(all_media: List[Dict[str, Any]], client_name: str, since: str, until: str) -> None:
    try:
        folder_path = os.path.join("media", client_name)
        os.makedirs(folder_path, exist_ok=True)

        filename = f"media_report_{since}_{until}.csv"
        file_path = os.path.join(folder_path, filename)

        headers = ["id", "media_type", "caption", "timestamp", "permalink", "children"]

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            for m in all_media:
                if not isinstance(m, dict):
                    print(f"[⚠️] Errore nella riga con ID: N/A → elemento non è un dizionario ({type(m)})")
                    continue

                try:
                    # Estrai figli in modo flessibile
                    children = m.get("children", None)

                    if isinstance(children, list):
                        children_ids = ";".join(child.get("id", "") for child in children)

                    elif isinstance(children, dict) and "data" in children:
                        children_data = children.get("data", [])
                        children_ids = ";".join(child.get("id", "") for child in children_data)

                    else:
                        children_ids = ""

                    row = {
                        "id": m.get("id", ""),
                        "media_type": m.get("media_type", ""),
                        "caption": m.get("caption", ""),
                        "timestamp": m.get("timestamp", ""),
                        "permalink": m.get("permalink", ""),
                        "children": children_ids
                    }

                    writer.writerow(row)

                except Exception as inner_e:
                    print(f"[⚠️] Errore nella riga con ID: {m.get('id', 'N/A')} → {inner_e}")

    except Exception as e:
        print(f"[❌] Errore durante il salvataggio CSV per {client_name}: {e}")


def save_text_report(report_text: str, client_name: str, since: str, until: str, report_name: str) -> None:
    """
    Salva un report testuale in un file .txt nella cartella output per il cliente.

    :param report_text: contenuto testuale da salvare
    :param client_name: nome cliente
    :param since: data inizio (YYYY-MM-DD)
    :param until: data fine (YYYY-MM-DD)
    :param report_name: nome descrittivo per il report (es. 'publication_frequency_report')
    """
    try:
        folder_path = os.path.join("output", client_name)
        os.makedirs(folder_path, exist_ok=True)

        filename = f"{report_name}_{since}_{until}.txt"
        file_path = os.path.join(folder_path, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        print(f"[💾] Report '{report_name}' salvato in {file_path}")

    except Exception as e:
        print(f"[❌] Errore durante il salvataggio report '{report_name}' per {client_name}: {e}")
