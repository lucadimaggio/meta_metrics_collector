from typing import Tuple
from copy import deepcopy
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image, UnidentifiedImageError
import io
import logging
import os

logger = logging.getLogger(__name__)


def register_font(name: str, path: str):
    """
    Registra un font personalizzato in ReportLab.
    :param name: Nome del font da usare poi in add_text.
    :param path: Percorso del file .ttf del font.
    """
    try:
        pdfmetrics.registerFont(TTFont(name, path))
        logger.info(f"Font '{name}' registrato da '{path}'.")
    except Exception as e:
        logger.error(f"Errore registrando font '{name}': {e}")


def load_template(path: str) -> PdfReader:
    """
    Carica il template PDF di base per sola lettura.
    ATTENZIONE: funzione per sola lettura.
    :param path: Percorso del file PDF template.
    :return: PdfReader contenente le pagine del template.
    """
    if not os.path.isfile(path):
        logger.error(f"Template PDF non trovato: {path}")
        raise FileNotFoundError(f"Template PDF non trovato: {path}")
    try:
        pdf = PdfReader(path)
        logger.info(f"Template PDF caricato da '{path}', pagine: {len(pdf.pages)}.")
        return pdf
    except Exception as e:
        logger.error(f"Errore caricando template PDF '{path}': {e}")
        raise


def duplicate_template(template_path: str, copies: int) -> PdfWriter:
    """
    Duplica la prima pagina del template per creare un PDF multipagina.
    :param template_path: Percorso del file PDF template.
    :param copies: Numero di copie da creare.
    :return: PdfWriter pronto per modifiche.
    """
    template_pdf = load_template(template_path)
    if len(template_pdf.pages) != 1:
        logger.warning("Template PDF contiene più di una pagina. Verrà usata solo la prima.")

    writer = PdfWriter()
    base_page = deepcopy(template_pdf.pages[0])

    for i in range(copies):
        writer.add_page(deepcopy(base_page))
    logger.info(f"Template duplicato {copies} volte.")
    return writer


def add_text(pdf_writer: PdfWriter, text: str, page_index: int, position: Tuple[int, int],
             font: str = "Helvetica", size: int = 12, align: str = "left",
             color: Tuple[float, float, float] = (0, 0, 0)):
    """
    Aggiunge testo in posizione specifica su pagina PDF (multipagina supportata).
    Supporta l’allineamento orizzontale: "left" (default) o "center".
    Supporta il colore testo RGB con valori da 0 a 1.
    """
    try:
        logger.debug(f"add_text: pagina {page_index}, testo: '{text}', posizione: {position}, font: {font}, size: {size}, align: {align}, color: {color}")
        if not isinstance(pdf_writer, PdfWriter):
            raise TypeError("pdf_writer deve essere un'istanza di PdfWriter.")
        if page_index >= len(pdf_writer.pages) or page_index < 0:
            raise IndexError(f"page_index {page_index} fuori range (0-{len(pdf_writer.pages)-1}).")

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(1920, 1080))
        can.setFont(font, size)

        # Set color
        r, g, b = color
        can.setFillColorRGB(r, g, b)
        logger.debug(f"add_text: colore impostato a RGB({r}, {g}, {b})")

        line_height = size * 1.2
        x, y = position
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line_y = y - i * line_height
            if align == "center":
                text_width = pdfmetrics.stringWidth(line, font, size)
                x_pos = x - (text_width / 2)
            else:
                x_pos = x
            can.drawString(x_pos, line_y, line)
            logger.debug(f"add_text: riga {i+1}/{len(lines)} '{line}' a ({x_pos}, {line_y}), font={font}, size={size}, align={align}")

        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]
        pdf_writer.pages[page_index].merge_page(overlay_page)
        logger.debug("add_text: merge pagina completato con successo")
        logger.debug("add_text: testo aggiunto con successo.")
    except Exception as e:
        logger.error(f"Errore in add_text: {e}")


def add_image(pdf_writer: PdfWriter, image_path: str, page_index: int, position: Tuple[int, int],
              size: Tuple[int, int]):
    """
    Inserisce un'immagine mantenendo proporzioni, gestendo errori di caricamento.
    """
    try:
        logger.debug(f"add_image: pagina {page_index}, immagine: '{image_path}', posizione: {position}, size: {size}")
        if not isinstance(pdf_writer, PdfWriter):
            raise TypeError("pdf_writer deve essere un'istanza di PdfWriter.")
        if page_index >= len(pdf_writer.pages) or page_index < 0:
            raise IndexError(f"page_index {page_index} fuori range (0-{len(pdf_writer.pages)-1}).")
        if not os.path.isfile(image_path):
            raise FileNotFoundError(f"File immagine non trovato: {image_path}")

        img = Image.open(image_path)
        img_width, img_height = img.size
        logger.debug(f"add_image: apertura immagine '{image_path}', dimensioni originali: {img_width}x{img_height}")

        box_width, box_height = size
        ratio = min(box_width / img_width, box_height / img_height)

        new_width = img_width * ratio
        new_height = img_height * ratio

        x = position[0] + (box_width - new_width) / 2
        y = position[1] + (box_height - new_height) / 2

        logger.debug(f"add_image: rapporto ridimensionamento: {ratio:.3f}, dimensioni adattate: {new_width:.1f}x{new_height:.1f}")
        logger.debug(f"add_image: posizione finale immagine (x={x:.1f}, y={y:.1f})")

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(1920, 1080))
        can.drawImage(image_path, x, y, width=new_width, height=new_height, preserveAspectRatio=True, mask='auto')
        logger.debug("add_image: inizio salvataggio overlay canvas")

        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]
        pdf_writer.pages[page_index].merge_page(overlay_page)
        logger.debug("add_image: immagine aggiunta con successo.")

    except FileNotFoundError as fnf_err:
        logger.error(f"File immagine non trovato: {fnf_err}")
    except UnidentifiedImageError as img_err:
        logger.error(f"Errore immagine non riconosciuta o corrotta: {img_err}")
    except Exception as e:
        logger.error(f"Errore in add_image: {e}")


def add_hyperlink(pdf_writer: PdfWriter, text: str, page_index: int, position: Tuple[int, int],
                  font: str = "Helvetica", size: int = 12, url: str = "", align: str = "left",
                  color: Tuple[float, float, float] = (0, 0, 0), underline: bool = False):
    """
    Inserisce testo con hyperlink cliccabile nel PDF.
    :param pdf_writer: PdfWriter su cui lavorare.
    :param text: Testo da mostrare cliccabile.
    :param page_index: Indice pagina PDF.
    :param position: Tuple (x, y) per posizione testo (origine in basso a sinistra).
    :param font: Nome font.
    :param size: Dimensione font.
    :param url: URL del link cliccabile.
    :param align: Allineamento orizzontale "left" o "center".
    :param color: Colore RGB (r,g,b) valori 0-1.
    :param underline: Se True, sottolinea il testo.
    """
    try:
        logger.debug(f"add_hyperlink: pagina {page_index}, testo: '{text}', url: {url}, posizione: {position}, font: {font}, size: {size}, align: {align}, color: {color}, underline: {underline}")
        if not isinstance(pdf_writer, PdfWriter):
            raise TypeError("pdf_writer deve essere un'istanza di PdfWriter.")
        if page_index >= len(pdf_writer.pages) or page_index < 0:
            raise IndexError(f"page_index {page_index} fuori range (0-{len(pdf_writer.pages)-1}).")
        if not url:
            logger.warning("add_hyperlink: URL vuoto, link non aggiunto.")

        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=(1920, 1080))
        can.setFont(font, size)
        r, g, b = color
        can.setFillColorRGB(r, g, b)
        logger.debug(f"add_hyperlink: colore impostato a RGB({r}, {g}, {b})")

        x, y = position
        lines = text.split('\n')
        line_height = size * 1.2

        for i, line in enumerate(lines):
            line_y = y - i * line_height
            text_width = pdfmetrics.stringWidth(line, font, size)
            if align == "center":
                x_pos = x - (text_width / 2)
            else:
                x_pos = x

            can.drawString(x_pos, line_y, line)
            logger.debug(f"add_hyperlink: riga {i+1}/{len(lines)} '{line}' a ({x_pos}, {line_y}), font={font}, size={size}, align={align}")

            if underline:
                text_width = pdfmetrics.stringWidth(line, font, size)
                underline_y = line_y - 2  # circa 2 punti sotto la baseline del testo
                can.setStrokeColorRGB(1, 1, 1)  # imposta il colore della linea a bianco
                can.setLineWidth(1)             # opzionale, imposta lo spessore della linea
                can.line(x_pos, underline_y, x_pos + text_width, underline_y)
                logger.debug(f"add_hyperlink: sottolineatura bianca aggiunta per '{line}' a ({x_pos}, {underline_y})")

            # Definisci area rettangolare cliccabile per ogni riga di testo
            rect = (x_pos, line_y, x_pos + text_width, line_y + size)
            can.linkURL(url, rect, relative=0)
            logger.debug(f"add_hyperlink: link URL '{url}' aggiunto nell’area {rect}")

        can.save()

        packet.seek(0)
        overlay_pdf = PdfReader(packet)
        overlay_page = overlay_pdf.pages[0]
        pdf_writer.pages[page_index].merge_page(overlay_page)
        logger.debug("add_hyperlink: link aggiunto con successo.")

    except Exception as e:
        logger.error(f"Errore in add_hyperlink: {e}")


def save_pdf(pdf_writer: PdfWriter, output_path: str):
    """
    Salva il PDF modificato su disco.
    """
    try:
        with open(output_path, "wb") as output_file:
            pdf_writer.write(output_file)
        logger.info(f"PDF salvato con successo in '{output_path}'.")
    except Exception as e:
        logger.error(f"Errore salvando PDF in '{output_path}': {e}")
