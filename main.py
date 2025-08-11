import sys
import os
import argparse
import logging

from src import step1_setup
from src import step2_get_ig_user
from src import step3_get_media
from src import step4_analyze_content
from src import step5_extract_pdf_fields
from src import step6_prepare_images
from src import step7_prepare_data
from src import step8_generate_pdf

from utils.token_utils import load_token
from utils.logger import get_logger
from utils.client_utils import save_client_data, load_client_data


# Parser CLI
parser = argparse.ArgumentParser()
parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Set log level (DEBUG, INFO, WARNING, ERROR)")
parser.add_argument("--yes-all", action="store_true", help="Esegue tutti gli step senza chiedere conferma")
parser.add_argument("--client-name", type=str, help="Nome cliente da analizzare")
parser.add_argument("--since", type=str, help="Data inizio analisi (YYYY-MM-DD)")
parser.add_argument("--until", type=str, help="Data fine analisi (YYYY-MM-DD)")
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
    logger.info("▶ Avvio esecuzione main.py")

    try:
        # Carica token
        logger.info("🔑 Caricamento token di accesso...")
        access_token = load_token()
        logger.info("✅ Token caricato con successo.")



        logger.info("📋 Richiesta dati cliente e configurazione...")
        config = step1_setup.get_user_input()
        client_name = config.get("client_name")
        since = config.get("since")
        until = config.get("until")
        logger.info(f"📋 Client scelto: {client_name}")
        logger.info(f"📅 Intervallo date: {since} - {until}")


        # Step 1: Setup cliente e configurazione
        logger.info("▶ Inizio Step 1: Setup cliente")
        config = step1_setup.run_step1(client_name, access_token, since, until)
        logger.info("✔ Step 1 completato.")
        if not args.yes_all:
            ask_to_continue(1, logger)

        since_unix = config.get("since_unix")
        until_unix = config.get("until_unix")
        logger.info(f"[DEBUG] since_unix: {since_unix}, until_unix: {until_unix}")


        # Step 2: Recupero IG User ID
        logger.info("▶ Inizio Step 2: Recupero IG User ID")
        config = step2_get_ig_user.run_step2(config)
        logger.info("✔ Step 2 completato.")
        if not args.yes_all:
            ask_to_continue(2, logger)

        # Step 3: Recupero media Instagram
        logger.info("▶ Inizio Step 3: Recupero media Instagram")
        all_media = step3_get_media.run_step3(config)
        config["media"] = all_media

        logger.info(f"✔ Step 3 completato. Trovati {len(all_media)} media.")
        if not args.yes_all:
            ask_to_continue(3, logger)

        # Step 4: Analisi contenuti
        logger.info("▶ Inizio Step 4: Analisi contenuti")
        logger.info(f"[DEBUG] Chiamata Step 4 con parametro until: {until}")
        step4_analyze_content.run_analysis(client_name, since, until)
        logger.info("✔ Step 4 completato.")
        if not args.yes_all:
            ask_to_continue(4, logger)

        # Step 5: Estrai top post per PDF
        logger.info("▶ Inizio Step 5: Estrazione top post")
        step5_extract_pdf_fields.extract_top_posts(config["client_name"], since, until)
        logger.info("✔ Step 5 completato.")
        if not args.yes_all:
            ask_to_continue(5, logger)

        # Step 6: Prepara immagini per PDF
        logger.info("▶ Inizio Step 6: Preparazione immagini")
        step6_prepare_images.prepare_images(config["client_name"], since, until, config["access_token"])
        logger.info("✔ Step 6 completato.")
        if not args.yes_all:
            ask_to_continue(6, logger)

        # Step 7: Prepara dati PDF
        logger.info("▶ Inizio Step 7: Preparazione dati PDF")
        step7_prepare_data.prepare_data(config["client_name"], since, until)
        logger.info("✔ Step 7 completato.")
        if not args.yes_all:
            ask_to_continue(7, logger)

        # Step 8: Genera PDF finale
        logger.info("▶ Inizio Step 8: Generazione PDF")
        step8_generate_pdf.generate_pdf(config["client_name"], since, until)
        logger.info(f"✔ Step 8 completato. PDF generato in output/{config['client_name']}/analisi_post_{since}_{until}.pdf")

        logger.info("✔ Esecuzione main.py completata con successo.")

    except Exception as e:
        logger.error(f"❌ Errore critico durante l'esecuzione: {e}")
        sys.exit(1)
