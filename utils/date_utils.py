import re
import datetime
import logging

logger = logging.getLogger(__name__)

def ask_date(prompt: str) -> str:
    """
    Chiede all'utente una data in formato GG-MM-AAAA o GG/MM/AAAA,
    la valida e restituisce una stringa ISO YYYY-MM-DD.
    """
    while True:
        date_input = input(f"📆 {prompt} (GG-MM-AAAA o GG/MM/AAAA): ").strip()
        date_input = date_input.replace("/", "-")
        if re.match(r"^\d{2}-\d{2}-\d{4}$", date_input):
            try:
                day, month, year = map(int, date_input.split("-"))
                datetime.date(year, month, day)  # valida la data
                return f"{year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                print("❌ Data non valida. Riprova.")
        else:
            print("❌ Formato non valido. Usa GG-MM-AAAA o GG/MM/AAAA.")


def generate_date_range(since: str, until: str) -> list[datetime.date]:
    """
    Genera una lista di date giornaliere tra since e until (inclusi),
    entrambi in formato ISO 'YYYY-MM-DD'.

    Logga la data di inizio, fine e il numero totale di date generate.

    :param since: data inizio range ISO string
    :param until: data fine range ISO string
    :return: lista di oggetti datetime.date
    """
    try:
        start_date = datetime.datetime.strptime(since, "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(until, "%Y-%m-%d").date()
    except Exception as e:
        logger.error(f"Errore nel parsing delle date in generate_date_range: since='{since}', until='{until}' - {e}")
        raise

    if end_date < start_date:
        logger.warning(f"La data 'until' {end_date} è precedente a 'since' {start_date}. Restituisco lista vuota.")
        return []

    delta_days = (end_date - start_date).days + 1
    date_list = [start_date + datetime.timedelta(days=i) for i in range(delta_days)]

    logger.info(f"generate_date_range: da {start_date} a {end_date}, totale date generate: {len(date_list)}")
    return date_list


def parse_date_only(date_str: str) -> datetime.date:
    """
    Estrae la parte data (anno, mese, giorno) da una stringa ISO o simile,
    ignorando l'eventuale orario o timezone.
    Logga errori di parsing.

    :param date_str: stringa data in formato ISO o simile
    :return: oggetto datetime.date
    :raises: ValueError se parsing fallisce
    """
    try:
        # Usa regex per estrarre YYYY-MM-DD all'inizio della stringa
        match = re.match(r"(\d{4}-\d{2}-\d{2})", date_str)
        if not match:
            raise ValueError(f"Formato data non valido: '{date_str}'")

        date_part = match.group(1)
        parsed_date = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
        logger.info(f"parse_date_only: estratta data {parsed_date} da '{date_str}'")
        return parsed_date

    except Exception as e:
        logger.error(f"Errore nel parsing data in parse_date_only con input '{date_str}': {e}")
        raise
