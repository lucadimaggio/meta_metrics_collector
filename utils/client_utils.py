import os
import json
import difflib
from datetime import datetime

CLIENTI_JSON = "config/clienti.json"

# 📥 Carica nomi cliente da /media e da clienti.json
def load_client_names():
    existing_dirs = set(os.listdir("media")) if os.path.exists("media") else set()
    existing_clients = set()

    if os.path.exists(CLIENTI_JSON):
        with open(CLIENTI_JSON, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                existing_clients = set(data.keys())
            except json.JSONDecodeError:
                pass

    return list(existing_dirs.union(existing_clients))


# 🔍 Trova nomi simili a quello inserito
def find_similar_names(input_name, all_names, cutoff=0.6):
    matches = difflib.get_close_matches(input_name.lower(), [n.lower() for n in all_names], n=5, cutoff=cutoff)
    results = []
    for match in matches:
        similarity = difflib.SequenceMatcher(None, input_name.lower(), match).ratio()
        results.append((match, int(similarity * 100)))
    return results


# ✅ Controllo nomi cliente
def check_client_name(input_name):
    all_clients = load_client_names()
    similars = find_similar_names(input_name, all_clients)

    if similars:
        print(f"\n⚠️  Trovati nomi simili a '{input_name}':")
        for name, score in similars:
            print(f"   - {name} (similitudine: {score}%)")

        while True:
            choice = input("👉 Vuoi procedere comunque con questo nome? (s = sì, n = no): ").strip().lower()
            if choice == "s":
                return input_name
            elif choice == "n":
                second = input("🔁 Vuoi reinserire un altro nome? (s = sì, n = esci): ").strip().lower()
                if second == "s":
                    nuovo = input("👤 Inserisci un nuovo nome cliente: ").strip()
                    return check_client_name(nuovo)
                else:
                    print("🚪 Uscita dal programma.")
                    exit(0)

    return input_name


# 💾 Salvataggio dati cliente
def save_client_data(client_name, page_id, data):
    if not os.path.exists(CLIENTI_JSON):
        clienti = {}
    else:
        with open(CLIENTI_JSON, "r", encoding="utf-8") as f:
            try:
                clienti = json.load(f)
            except json.JSONDecodeError:
                clienti = {}

    # Debug log
    print(f"[💾] Salvataggio: {client_name} - data: {data}")

    # ✅ Validazione IG User ID
    ig_user_id = data.get("ig_user_id")
    if isinstance(ig_user_id, dict):
        print("❌ Errore: ig_user_id ricevuto come dict. Verifica dove viene passato.")
        return
    elif not isinstance(ig_user_id, str):
        ig_user_id = str(ig_user_id)
        print("ℹ️ ig_user_id convertito forzatamente in stringa.")

    # ✅ Validazione date
    def validate_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            print(f"⚠️  Data non valida o assente: '{date_str}' → Ignorata.")
            return None

    entry = {
        "page_id": str(data.get("page_id", "")),
        "ig_user_id": ig_user_id
    }

    since = validate_date(data.get("last_since"))
    until = validate_date(data.get("last_until"))
    if since:
        entry["last_since"] = since
    if until:
        entry["last_until"] = until

    if client_name in clienti:
        print(f"[ℹ️] Cliente '{client_name}' aggiornato.")
    else:
        print(f"[➕] Nuovo cliente '{client_name}' aggiunto.")

    clienti[client_name] = entry

    with open(CLIENTI_JSON, "w", encoding="utf-8") as f:
        json.dump(clienti, f, indent=2, ensure_ascii=False)


# 📤 Caricamento dati cliente
def load_client_data(client_name):
    if not os.path.exists(CLIENTI_JSON):
        return {}

    with open(CLIENTI_JSON, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return {}

    return data.get(client_name, {})
