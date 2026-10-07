"""Flight price agent: Raipur (RPR) -> Bangalore (BLR) on Nov 10 / Nov 11, 2026.
Each run: fetch prices via SerpAPI Google Flights, append to prices.csv,
and send a Telegram alert (optional) with the cheapest option + change vs last run.
"""
import csv, os, datetime as dt, requests

ORIGIN, DEST = "RPR", "BLR"
DATES = ["2026-11-10", "2026-11-11"]
CSV_FILE = "prices.csv"
SERPAPI_KEY = os.environ["SERPAPI_KEY"]
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID")


def cheapest(date):
    r = requests.get("https://serpapi.com/search.json", params={
        "engine": "google_flights", "departure_id": ORIGIN, "arrival_id": DEST,
        "outbound_date": date, "type": 2, "currency": "INR", "hl": "en",
        "api_key": SERPAPI_KEY}, timeout=60)
    r.raise_for_status()
    d = r.json()
    options = (d.get("best_flights") or []) + (d.get("other_flights") or [])
    options = [o for o in options if "price" in o]
    if not options:
        return None
    best = min(options, key=lambda o: o["price"])
    legs = best["flights"]
    return {
        "price": best["price"],
        "airline": " + ".join(dict.fromkeys(l["airline"] for l in legs)),
        "depart": legs[0]["departure_airport"]["time"],
        "arrive": legs[-1]["arrival_airport"]["time"],
        "stops": len(legs) - 1,
    }


def last_price(date):
    if not os.path.exists(CSV_FILE):
        return None
    rows = [r for r in csv.DictReader(open(CSV_FILE)) if r["flight_date"] == date]
    return int(rows[-1]["price"]) if rows else None


def notify(text):
    print(text)
    if TG_TOKEN and TG_CHAT:
        requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                      data={"chat_id": TG_CHAT, "text": text}, timeout=30)


def main():
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    new_file = not os.path.exists(CSV_FILE)
    lines, results = [], []
    for date in DATES:
        prev = last_price(date)
        try:
            res = cheapest(date)
        except Exception as e:
            lines.append(f"{date}: error ({e})")
            continue
        if not res:
            lines.append(f"{date}: no flights found")
            continue
        delta = "" if prev is None else f" ({res['price'] - prev:+d} vs last)"
        lines.append(f"{date}: ₹{res['price']}{delta} · {res['airline']} · "
                     f"{res['depart']}→{res['arrive']} · {res['stops']} stop(s)")
        results.append((date, res))
    with open(CSV_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["checked_at_utc", "flight_date", "price", "airline", "depart", "arrive", "stops"])
        for date, r in results:
            w.writerow([now, date, r["price"], r["airline"], r["depart"], r["arrive"], r["stops"]])
    if results:
        d, r = min(results, key=lambda x: x[1]["price"])
        lines.append(f"\nCheapest: {d} at ₹{r['price']}")
    notify(f"✈️ {ORIGIN}→{DEST}\n" + "\n".join(lines))


if __name__ == "__main__":
    main()
