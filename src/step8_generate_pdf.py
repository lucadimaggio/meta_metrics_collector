import os
import sys
import json
from datetime import datetime
from PIL import Image
from utils.pdf_utils import duplicate_template, add_text, add_hyperlink, add_image, save_pdf, register_font, PdfWriter
from utils.pdf_utils import load_template

from utils.logger import get_logger, log_exceptions

logger = get_logger(__name__)

@log_exceptions
def generate_pdf(client_name, since, until):
    """
    Genera un PDF multipagina a partire dal JSON con i percorsi locali delle immagini già aggiornati.
    Headline: testo fisso "Analisi Contenuti", allineamento a sinistra, margine fisso 80 px.
    """
    json_path = f"output/{client_name}/pdf_fields_{since}_{until}_with_images.json"
    output_path = f"output/{client_name}/analisi_post_{since}_{until}.pdf"
    template_path = "templates/template_post.pdf"

    if not os.path.exists(json_path):
        logger.error(f"File JSON non trovato: {json_path}")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        top_posts = json.load(f)

    if not isinstance(top_posts, list) or len(top_posts) == 0:
        logger.error("Nessun top post trovato nel JSON o formato errato (lista attesa).")
        return

    # Registra font disponibili
    register_font("Montserrat-Regular", "fonts/Montserrat-Regular.ttf")
    register_font("Montserrat-Bold", "fonts/Montserrat-Bold.ttf")

    pdf_final = PdfWriter()

    template_pdf = load_template(template_path)
    mediabox = template_pdf.pages[0].mediabox
    page_width = float(mediabox.right) - float(mediabox.left)
    page_height = float(mediabox.top) - float(mediabox.bottom)

    # Configurazioni headline fisse richieste
    headline_text = "Analisi Contenuti"
    uppercase = True
    headline_color = (1, 1, 1)  # bianco RGB normalizzato
    headline_font = "Montserrat-Bold"
    headline_size = 80
    align = "left"
    headline_x = 80  # margine fisso a sinistra
    headline_y = page_height - headline_size - 30  # posizione verticale calcolata

    for idx, post in enumerate(top_posts[:3]):
        pdf_page = duplicate_template(template_path, 1)
        logger.info(f"Generata pagina {idx + 1} per post del {post.get('data', 'data sconosciuta')}")

        title_text = headline_text.upper() if uppercase else headline_text

        add_text(pdf_page, title_text, 0, (headline_x, headline_y), headline_font, headline_size, align=align, color=headline_color)

        image_path = post.get("local_img_path")
        if image_path and os.path.exists(image_path):
            with Image.open(image_path) as img:
                width_px, height_px = img.size

            # Fisso percentuale altezza al 50%
            perc_height = 50
            height_pdf = page_height * (perc_height / 100)
            width_pdf = (width_px / height_px) * height_pdf

            # Fisso x a 80
            x_pos = 80
            # Calcolo y per centrare verticalmente
            y_pos = (page_height - height_pdf) / 2

            add_image(pdf_page, image_path, 0, (x_pos, y_pos), (width_pdf, height_pdf))

            # Calcolo X per metriche (60px a destra immagine)
            metrics_x = x_pos + width_pdf + 60

            # Fisso la coordinata Y per testo metriche a 135
            metrics_y = 135
            logger.info(f"Coordinata Y per testo metriche impostata fissa a: {metrics_y}")

            placeholder_positions = {
                "metrics": {
                    "x": metrics_x,
                    "y": metrics_y,
                    "width": 700,
                    "height": 540,
                    "font": "Montserrat-Regular",
                    "size": 24,
                    "line_height": 28,
                    "color": (1, 1, 1)
                }
            }

            pos_metrics = placeholder_positions["metrics"]
            x_text = pos_metrics["x"]

            # Format timestamp from YYYY-MM-DD to DD/MM/YYYY
            timestamp_str = post.get('timestamp', '')
            if timestamp_str:
                try:
                    dt = datetime.strptime(timestamp_str, "%Y-%m-%d")
                    formatted_date = dt.strftime("%d/%m/%Y")
                except Exception:
                    formatted_date = timestamp_str  # se formato errato, lascia com’è
            else:
                formatted_date = ""

            media_type = post.get("media_type", "").lower()

            metrics_lines = [
                f"Data: {formatted_date}",
                f"Score: {post.get('quality_score', '')}",
                f"Shares: {post.get('shares', 'N/A')}",
                f"Reach: {post.get('reach', 'N/A')}",
                f"Saved: {post.get('saved', 'N/A')}",
            ]

            if media_type != "image":
                metrics_lines.append(f"Video views: {post.get('video_views', 'N/A')}")

            metrics_lines.extend([
                f"Like count: {post.get('like_count', 'N/A')}",
                f"Comments count: {post.get('comments_count', 'N/A')}",
                f"Total interactions: {post.get('total_interactions', 'N/A')}",
                "Link al post"
            ])

            

            total_text_height = len(metrics_lines) * pos_metrics["line_height"]
            y_center = pos_metrics["y"] + pos_metrics["height"] / 2
            y_start = y_center + total_text_height / 2 - pos_metrics["line_height"]

            for i, line in enumerate(metrics_lines):
                y = y_start - i * pos_metrics["line_height"]
                if line == "Link al post":
                    url = post.get('media_url', '')
                    if url:
                        add_hyperlink(
                            pdf_page,
                            line,
                            0,
                            (x_text, y),
                            pos_metrics["font"],
                            pos_metrics["size"],
                            url,
                            color=pos_metrics.get("color", (0, 0, 0)),
                            underline=True
                        )
                        logger.info(f"Inserito link cliccabile pagina {idx + 1}: testo '{line}' in posizione ({x_text}, {y}), URL: {url}")
                    else:
                        add_text(pdf_page, line, 0, (x_text, y), pos_metrics["font"], pos_metrics["size"], color=pos_metrics.get("color", (0, 0, 0)))
                        logger.warning(f"URL mancante per link cliccabile nel post {idx + 1}. Inserito solo testo '{line}'.")
                else:
                    add_text(pdf_page, line, 0, (x_text, y), pos_metrics["font"], pos_metrics["size"], color=pos_metrics.get("color", (0, 0, 0)))
                    logger.info(f"Inserito testo metriche pagina {idx + 1}: '{line}' in posizione ({x_text}, {y})")

        else:
            logger.warning(f"Immagine mancante o non trovata per post {idx + 1}: {image_path}")
            logger.info(f"Salto inserimento immagine pagina {idx + 1} per mancanza file.")
            continue

        pdf_final.add_page(pdf_page.pages[0])
        logger.info(f"Aggiunta pagina {idx + 1} al PDF finale.")

    if pdf_final.pages:
        os.makedirs(f"output/{client_name}", exist_ok=True)
        save_pdf(pdf_final, output_path)
        logger.info(f"PDF multipagina generato con {len(pdf_final.pages)} pagine: {output_path}")
    else:
        logger.warning("PDF non generato: nessuna pagina creata.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        logger.error("Usage: python src/step8_generate_pdf.py <client_name> <since> <until>")
        logger.info("Example: python src/step8_generate_pdf.py 55Bijoux 2025-07-01 2025-07-25")
        sys.exit(1)

    client_name = sys.argv[1]
    since = sys.argv[2]
    until = sys.argv[3]
    generate_pdf(client_name, since, until)
