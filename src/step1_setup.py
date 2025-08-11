import os
from datetime import datetime, timezone
from utils.client_utils import (
    check_client_name,
    save_client_data,
    load_client_data,
    load_client_names
)
from utils.date_utils import ask_date
from utils.logger import get_logger

logger = get_logger(__name__)

from datetime import timedelta

def split_date_range_into_months(since_str, until_str):
    """
    Riceve due stringhe date YYYY-MM-DD e ritorna una lista di tuple (start, end)
    che coprono l'intervallo diviso in mesi.
    """
    intervals = []
    start_date = datetime.strptime(since_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(until_str, "%Y-%m-%d").date()

    current_start = start_date

    while current_start <= end_date:
        # Calcola fine mese corrente o fine intervallo
        if current_start.month == 12:
            next_month = datetime(current_start.year + 1, 1, 1).date()
        else:
            next_month = datetime(current_start.year, current_start.month + 1, 1).date()

        current_end = next_month - timedelta(days=1)
        if current_end > end_date:
            current_end = end_date

        intervals.append((
            current_start.strftime("%Y-%m-%d"),
            current_end.strftime("%Y-%m-%d")
        ))

        current_start = current_end + timedelta(days=1)

    logger.info(f"Intervallo {since_str} - {until_str} suddiviso in {len(intervals)} intervalli mensili:")
    for s, u in intervals:
        logger.debug(f"  Sotto-intervallo: {s} → {u}")

    return intervals


def get_user_input():
    print("Vuoi:")
    print("1 - Visualizzare i clienti esistenti")
    print("2 - Inserire un nuovo cliente")
    
    while True:
        scelta = input("👉 Scrivi 1 o 2: ").strip()
        logger.debug(f"Input scelta iniziale: {scelta}")
        if scelta in ["1", "2"]:
            logger.info(f"Scelta valida ricevuta: {scelta}")
            break
        logger.warning(f"Scelta non valida: {scelta}")
        print("❌ Scelta non valida. Digita 1 o 2.")

    # 🧭 SCELTA 1: CLIENTE GIÀ ESISTENTE
    if scelta == "1":
        nomi_clienti = load_client_names()
        if not nomi_clienti:
            logger.info("Nessun cliente trovato. Passo all'inserimento manuale.")
            print("⚠️ Nessun cliente trovato. Passo all'inserimento manuale.")
            scelta = "2"
        else:
            print("\n📋 Clienti esistenti:")
            for idx, nome in enumerate(nomi_clienti, 1):
                print(f"{idx}. {nome}")

            while True:
                scelta_cliente = input("\n✍️ Scrivi il nome esatto o il numero del cliente con cui vuoi procedere: ").strip()
                logger.debug(f"Input cliente esistente ricevuto: {scelta_cliente}")
                
                # Provo a interpretare come numero
                if scelta_cliente.isdigit():
                    idx = int(scelta_cliente)
                    if 1 <= idx <= len(nomi_clienti):
                        nome_cliente = nomi_clienti[idx - 1]
                        logger.info(f"Cliente selezionato per indice: {nome_cliente}")
                        break
                    else:
                        logger.warning(f"Indice cliente fuori range: {scelta_cliente}")
                        print("❌ Numero non valido. Riprova.")
                else:
                    # Interpreto come nome
                    if scelta_cliente in nomi_clienti:
                        nome_cliente = scelta_cliente
                        logger.info(f"Cliente selezionato per nome: {nome_cliente}")
                        break
                    else:
                        logger.warning(f"Nome cliente non trovato: {scelta_cliente}")
                        print("❌ Nome non trovato. Assicurati di scriverlo correttamente.")

            client_name = nome_cliente
            existing_data = load_client_data(client_name) or {}

            # ✅ Recupero dati da struttura piatta
            page_id = existing_data.get("page_id")
            ig_user_id = existing_data.get("ig_user_id")
            last_since = existing_data.get("since")
            last_until = existing_data.get("until")

            if not page_id or not page_id.isdigit():
                logger.warning(f"Nessun Page ID valido trovato per cliente {client_name}")
                print("⚠️ Nessun Page ID valido trovato per questo cliente. Passo all'inserimento manuale.")
                scelta = "2"
            else:
                page_ids = [page_id]
                print(f"\n📄 Page ID trovato: {page_id}")

                if last_since and last_until:
                    print(f"📅 Intervallo salvato: {last_since} → {last_until}")
                    reuse = input("🔁 Vuoi riutilizzarlo? (s/n): ").strip().lower()
                    if reuse == "s":
                        since = last_since
                        until = last_until
                    else:
                        since = ask_date("Data iniziale (dal)")
                        until = ask_date("Data finale (al)")
                else:
                    since = ask_date("Data iniziale (dal)")
                    until = ask_date("Data finale (al)")

                # Validazione e suddivisione intervallo
                start_dt = datetime.strptime(since, "%Y-%m-%d")
                end_dt = datetime.strptime(until, "%Y-%m-%d")

                if start_dt > end_dt:
                    logger.warning("La data iniziale è successiva a quella finale. Invertita automaticamente.")
                    since, until = until, since  # scambio per sicurezza
                    start_dt, end_dt = end_dt, start_dt

                diff_days = (end_dt - start_dt).days
                if diff_days > 31:
                    logger.info(f"Intervallo superiore a 1 mese ({diff_days} giorni). Suddivisione in intervalli mensili.")
                    date_intervals = split_date_range_into_months(since, until)
                else:
                    logger.info(f"Intervallo inferiore o uguale a 1 mese ({diff_days} giorni). Nessuna suddivisione.")
                    date_intervals = [(since, until)]



                return {
                    "client_name": client_name,
                    "page_ids": page_ids,
                    "since": since,
                    "until": until,
                    "date_intervals": date_intervals,  
                }


    # 🧭 SCELTA 2: NUOVO CLIENTE (flusso attuale)
    client_name = check_client_name(input("👤 Nome cliente (verrà creata una cartella con questo nome): "))
    existing_data = load_client_data(client_name) or {}

    existing_page_ids = [pid for pid in existing_data.keys() if pid.isdigit()]
    page_ids = []

    if existing_page_ids:
        print(f"📄 Page ID già presenti per {client_name}: {', '.join(existing_page_ids)}")
        reuse = input("🔁 Vuoi riutilizzarli? (s/n): ").strip().lower()
        if reuse == "s":
            page_ids = existing_page_ids

    if not page_ids:
        while True:
            page_ids_input = input("📄 Inserisci uno o più Page ID (delle pagine FB) separati da virgola: ").strip()
            page_ids = [p.strip() for p in page_ids_input.split(",") if p.strip().isdigit()]
            if page_ids:
                break
            print("❌ Inserisci almeno un Page ID valido (numerico). Riprova.")

    last_since = None
    last_until = None
    for page_id in page_ids:
        if page_id in existing_data and isinstance(existing_data[page_id], dict):
            last_since = existing_data[page_id].get("since")
            last_until = existing_data[page_id].get("until")
            break

    if last_since and last_until:
        print(f"📅 Ultimo intervallo usato: {last_since} → {last_until}")
        reuse_dates = input("🔁 Vuoi riutilizzarlo? (s/n): ").strip().lower()
        if reuse_dates == "s":
            since = last_since
            until = last_until
        else:
            since = ask_date("Data iniziale (dal)")
            until = ask_date("Data finale (al)")
    else:
        since = ask_date("Data iniziale (dal)")
        until = ask_date("Data finale (al)")

    # Validazione e suddivisione intervallo (stesso pattern scelta 1)
    start_dt = datetime.strptime(since, "%Y-%m-%d")
    end_dt = datetime.strptime(until, "%Y-%m-%d")

    if start_dt > end_dt:
        logger.warning("La data iniziale è successiva a quella finale. Invertita automaticamente.")
        since, until = until, since  # scambio per sicurezza
        start_dt, end_dt = end_dt, start_dt

    diff_days = (end_dt - start_dt).days
    if diff_days > 31:
        logger.info(f"Intervallo superiore a 1 mese ({diff_days} giorni). Suddivisione in intervalli mensili.")
        date_intervals = split_date_range_into_months(since, until)
    else:
        logger.info(f"Intervallo inferiore o uguale a 1 mese ({diff_days} giorni). Nessuna suddivisione.")
        date_intervals = [(since, until)]


    return {
        "client_name": client_name,
        "page_ids": page_ids,
        "since": since,
        "until": until,
        "date_intervals": date_intervals,  
    }


def date_to_unix(date_str):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    dt_utc = dt.replace(tzinfo=timezone.utc)
    return int(dt_utc.timestamp())


def prepare_directories(client_name):
    folders = [f"media/{client_name}", f"output/{client_name}"]
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"[INFO] Cartella pronta: {folder}")


def initialize(config):
    config['since_unix'] = date_to_unix(config['since'])
    config['until_unix'] = date_to_unix(config['until'])

    prepare_directories(config['client_name'])
    print("[CONFIG]", config)

    print(f"\n✅ Setup completato per '{config['client_name']}'")
    print(f"📅 Periodo: {config['since']} → {config['until']}")

def run_step1(client_name: str, access_token: str, since: str, until: str) -> dict:
    logger.info(f"Inizio setup step1 per cliente '{client_name}' con intervallo {since} - {until}")

    # Prepara cartelle necessarie per il cliente
    prepare_directories(client_name)
    logger.info(f"Cartelle create per il cliente '{client_name}'")

    # Carica dati esistenti cliente
    existing_data = load_client_data(client_name) or {}
    logger.info(f"Dati esistenti caricati per cliente '{client_name}': {existing_data}")

    # Recupera page_ids se presenti
    page_ids = []
    if "page_id" in existing_data and isinstance(existing_data["page_id"], str) and existing_data["page_id"].isdigit():
        page_ids = [existing_data["page_id"]]
    else:
        existing_page_ids = [pid for pid in existing_data.keys() if pid.isdigit()]
        if existing_page_ids:
            page_ids = existing_page_ids

    if page_ids:
        logger.info(f"Page ID trovati nei dati cliente: {page_ids}")
    else:
        logger.warning(f"Nessun Page ID trovato nei dati cliente '{client_name}'")


    # Validazione e eventuale inversione date se necessario
    start_dt = datetime.strptime(since, "%Y-%m-%d")
    end_dt = datetime.strptime(until, "%Y-%m-%d")
    if start_dt > end_dt:
        logger.warning("Data iniziale successiva a data finale, inversione automatica.")
        since, until = until, since
        start_dt, end_dt = end_dt, start_dt

    diff_days = (end_dt - start_dt).days

    # Suddivisione intervallo date in intervalli mensili se superiore a 31 giorni
    if diff_days > 31:
        logger.info(f"Intervallo superiore a 1 mese ({diff_days} giorni). Suddivisione in intervalli mensili.")
        date_intervals = split_date_range_into_months(since, until)
    else:
        logger.info(f"Intervallo entro 1 mese ({diff_days} giorni). Nessuna suddivisione.")
        date_intervals = [(since, until)]

    # Costruzione dizionario config da ritornare
    config = {
        "client_name": client_name,
        "access_token": access_token,
        "since": since,
        "until": until,
        "page_ids": page_ids,
        "date_intervals": date_intervals
    }

    logger.info(f"Setup step1 completato per cliente '{client_name}'. Config pronta.")
    logger.debug(f"Config: {config}")

    config["since_unix"] = date_to_unix(config["since"])
    config["until_unix"] = date_to_unix(config["until"])
    
    return config


    print(f"📄 Page IDs: {', '.join(config['page_ids'])}")
    print("📁 Cartelle create.\n")
