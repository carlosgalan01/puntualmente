"""Una foto de todos los trenes de Renfe en circulación, añadida al CSV del día (TFM)."""
import csv, datetime, json, pathlib, urllib.request

def leer(url):
    return json.load(urllib.request.urlopen(url, timeout=30))

ahora = datetime.datetime.now(datetime.timezone.utc)
filas = []
pos = leer("https://gtfsrt.renfe.com/vehicle_positions.json")
upd = leer("https://gtfsrt.renfe.com/trip_updates.json")
retraso = {e["tripUpdate"]["trip"]["tripId"]: e["tripUpdate"].get("delay", 0) for e in upd["entity"]}
for e in pos["entity"]:
    v = e["vehicle"]
    if "position" not in v:
        continue
    tid = v["trip"]["tripId"]
    filas.append(["cercanias", v.get("vehicle", {}).get("label", tid), v["position"]["latitude"], v["position"]["longitude"],
                  round(retraso.get(tid, 0) / 60), v.get("stopId", ""), v.get("currentStatus", ""), v.get("timestamp", "")])
ld = leer("https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json")
for t in ld["trenes"]:
    filas.append(["larga", t["codComercial"], t["latitud"], t["longitud"], t.get("ultRetraso") or 0,
                  t["codEstSig"], f'{t["codOrigen"]}>{t["codDestino"]}|{t["codProduct"]}', t["time"]])

f = pathlib.Path("datos") / f"{ahora:%Y-%m-%d}.csv"
nuevo = not f.exists()
with open(f, "a", newline="") as fh:
    w = csv.writer(fh)
    if nuevo:
        w.writerow(["foto_utc", "tipo", "tren", "lat", "lon", "retraso_min", "siguiente_parada", "extra", "hora_dato"])
    for r in filas:
        w.writerow([f"{ahora:%Y-%m-%dT%H:%M:%SZ}"] + r)
print(len(filas), "trenes")
# los avisos de incidencias, aparte y sólo si han cambiado
avisos = pathlib.Path("datos") / "avisos.json"
nuevos = leer("https://gtfsrt.renfe.com/alerts.json")
if not avisos.exists() or json.loads(avisos.read_text()).get("header") != nuevos.get("header"):
    avisos.write_text(json.dumps(nuevos, ensure_ascii=False))
