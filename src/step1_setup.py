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
                    logger.debug(f"Risposta riutilizzo date: {reuse}")
                    if reuse == "s":
                        since = last_since
                        until = last_until
                    else:
                        since = ask_date("Data iniziale (dal)")
                        until = ask_date("Data finale (al)")
                else:
                    since = ask_date("Data iniziale (dal)")
                    until = ask_date("Data finale (al)")

                return {
                    "client_name": client_name,
                    "page_ids": page_ids,
                    "since": since,
                    "until": until
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

    return {
        "client_name": client_name,
        "page_ids": page_ids,
        "since": since,
        "until": until
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
    print(f"📄 Page IDs: {', '.join(config['page_ids'])}")
    print("📁 Cartelle create.\n")
