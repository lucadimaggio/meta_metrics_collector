import os
import sys
import argparse
import datetime

from utils.logger import get_logger
import src.step1_setup as step1_setup
import src.step2_get_ig_user as step2_get_ig_user
import src.step3_get_media as step3_get_media
from utils.token_utils import load_token
from utils.client_utils import save_client_data, load_client_data
from src.step4_analyze_content import integrated_analysis
from src.step5_extract_pdf_fields import extract_top_posts
from src.step6_prepare_images import prepare_images
from src.step7_prepare_data import prepare_data
from src.step8_generate_pdf import generate_pdf

# Parser CLI
parser = argparse.ArgumentParser()
parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Set log level (DEBUG, INFO, WARNING, ERROR)")
parser.add_argument("--yes-all", action="store_true", help="Esegue tutti gli step senza chiedere conferma")
args, _ = parser.parse_known_args()

# Logger root
logger = get_logger("meta_metrics_collector")
logger.setLevel(args.log_level.upper())


def ask_to_continue(current_step: int, logger, auto_yes: bool = False):
    """
    Logga la fine dello step corrente e, se non è attivo --yes-all, chiede conferma prima di passare al successivo.
    """
    logger.info(f"✔ Step {current_step} completato")

    next_step = current_step + 1
    if auto_yes:
        logger.info(f"▶ Avvio Step {next_step}")
        return

    answer = input(f"Step {current_step} completato. Vuoi procedere con Step {next_step}? (s/n): ").strip().lower()
    if answer != "s":
        logger.warning(f"⏹ Esecuzione interrotta dopo lo Step {current_step}")
        sys.exit(0)

    logger.info(f"▶ Avvio Step {next_step}")


if __name__ == "__main__":
    # 1. Carica token
    access_token = load_token()

    # 2. Ottieni nome cliente e Page ID
    config = step1_setup.get_user_input()
    config["access_token"] = access_token

    # 3. Recupera IG User ID per ciascun Page ID
    ask_to_continue(1, logger, auto_yes=args.yes_all)
    config["client_data"] = {}

    for page_id in config["page_ids"]:
        ig_user_id = step2_get_ig_user.get_instagram_user_id(page_id, config["access_token"])
        if ig_user_id:
            logger.info(f"[✔] IG User ID trovato: {ig_user_id} per la pagina {page_id}")
        else:
            logger.warning(f"[!] Nessun IG collegato per la pagina {page_id}")

        config["client_data"][page_id] = {"ig_user_id": ig_user_id}

    # 4. Chiedi intervallo date SOLO se non esistono già dati salvati
    existing_client_data = load_client_data(config["client_name"])
    if existing_client_data and "last_since" in existing_client_data and "last_until" in existing_client_data:
        logger.info("[ℹ] Date trovate nei dati cliente salvati, le riutilizzo.")
        since = existing_client_data["last_since"]
        until = existing_client_data["last_until"]
    else:
        while True:
            since = step1_setup.ask_date("Data INIZIO")
            until = step1_setup.ask_date("Data FINE")

            since_dt = datetime.datetime.strptime(since, "%Y-%m-%d")
            until_dt = datetime.datetime.strptime(until, "%Y-%m-%d")

            if since_dt > until_dt:
                logger.error("❌ La data di inizio è successiva alla data di fine. Riprova.")
            else:
                break

    config["since"] = since
    config["until"] = until
    config["since_unix"] = step1_setup.date_to_unix(since)
    config["until_unix"] = step1_setup.date_to_unix(until)

    # 5. Salva dati cliente evitando duplicati
    page_id = config["page_ids"][0]  # Gestione di una sola pagina per cliente
    ig_user_id = config["client_data"][page_id]["ig_user_id"]

    if ig_user_id:
        logger.debug(f"DEBUG: page_id = {page_id} | ig_user_id = {ig_user_id}")
        if not (existing_client_data and existing_client_data.get("page_id") == page_id):
            save_client_data(config["client_name"], page_id, {
                "page_id": page_id,
                "ig_user_id": ig_user_id,
                "last_since": since,
                "last_until": until
            })
        else:
            logger.info("[ℹ] Dati cliente già salvati, nessun aggiornamento.")
    else:
        logger.warning("⚠️ IG User ID non valido: dati non salvati in clienti.json")

    # 6. Prepara struttura di cartelle e file
    ask_to_continue(2, logger, auto_yes=args.yes_all)
    step1_setup.initialize(config)

    # 7. Recupera media
    ask_to_continue(3, logger, auto_yes=args.yes_all)
    all_media = []

    for page_id in config["page_ids"]:
        ig_user_id = config["client_data"][page_id]["ig_user_id"]

        if not ig_user_id:
            logger.warning(f"[⏭] Skip: nessun IG User ID per {page_id}")
            continue

        media = step3_get_media.get_media_list(
            ig_user_id,
            config["access_token"],
            config["since_unix"],
            config["until_unix"],
            client_name = config["client_name"]

        )

        logger.info(f"[📸] Trovati {len(media)} media per {page_id}")
        all_media.extend(media)

    # 8. Analisi integrata dei media
    if all_media:
        try:
            logger.info("📊 Avvio analisi integrata dei contenuti...")
            integrated_analysis(all_media, since, until, config["client_name"])
            logger.info("📊 Analisi contenuti completata con successo")
        except Exception as e:
            logger.error(f"❌ Errore durante l'analisi integrata dei contenuti: {e}")
    else:
        logger.warning("[!] Nessun media trovato da analizzare.")

    # 9. Estrai top post
    ask_to_continue(4, logger, auto_yes=args.yes_all)
    extract_top_posts(config["client_name"], since, until)

    # 10. Prepara immagini per il PDF
    ask_to_continue(5, logger, auto_yes=args.yes_all)
    prepare_images(config["client_name"], since, until, config["access_token"])

    # 11. Genera PDF
    ask_to_continue(6, logger, auto_yes=args.yes_all)
    try:
        generate_pdf(config["client_name"], since, until)
        logger.info(f"[✅] PDF generato in output/{config['client_name']}/analisi_post_{since}_{until}.pdf")
    except Exception as e:
        logger.error(f"[❌] Errore durante la generazione del PDF: {e}")
