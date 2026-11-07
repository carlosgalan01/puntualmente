"""Entrena el modelo de Andén: cuánto retraso llevará cada tren dentro de unos minutos.

Lee fotos de la red (las tablas que graba la caja negra o una captura en JSON), arma ejemplos
«tren en el minuto t -> su retraso en t + horizonte», entrena una red neuronal pequeña y la compara
con la estimación ingenua de «seguirá igual». Exporta los pesos a JSON para que la web la ejecute.

Uso:  python entrenar.py --csv datos/*.csv --horizonte 30 --tendencia 5 --salida web/base/modelo.json
      python entrenar.py --captura carpeta_con_cp_tu_ld --horizonte 5 --tendencia 2 --salida ...
"""
import argparse, csv, datetime, glob, json, math, os, random, re
from collections import defaultdict

import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

ZONAS = ["Madrid", "Rodalies", "Asturias", "Bilbao", "Valencia", "Cantabria", "Sevilla", "Murcia/Alicante", "Málaga"]
PRODUCTOS = ["AVE", "ALVIA", "AVANT", "MD", "REGIONAL", "REG.EXP.", "AVLO", "Intercity"]
NUCLEOS = {"10": "Madrid", "20": "Asturias", "30": "Sevilla", "31": "Cádiz", "32": "Málaga", "40": "Valencia", "41": "Murcia/Alicante",
           "45": "Cartagena", "46": "Ferrol", "47": "León", "50": "Rodalies", "51": "Rodalies", "60": "Bilbao", "61": "San Sebastián",
           "62": "Cantabria", "70": "Zaragoza"}


# Renfe añade «-PLATF.(n)» al nombre de un tren mientras está en un andén: es el mismo tren
sin_anden = lambda s: re.sub(r"-PLATF\.\(.*\)$", "", s)


def sin_salto(d):
    """Renfe da el retraso de los trenes que cruzan la medianoche con un día de más o de menos (-1436 = 4 min)."""
    return d + 1440 if d < -720 else d - 1440 if d > 720 else d


def fotos_de_csv(rutas, prod):
    fotos = defaultdict(dict)
    for ruta in rutas:
        for f in csv.DictReader(open(ruta)):
            t = datetime.datetime.fromisoformat(f["foto_utc"].replace("Z", "+00:00")).timestamp()
            k = "l" if f["tipo"] == "larga" else "c"
            extra = f.get("extra", "")
            zona = NUCLEOS.get(extra.split("|")[1][:2], "") if k == "c" and "|" in extra else ""
            producto = prod.get(str(int(f["tren"]))) if k == "l" and f["tren"].isdigit() else ""
            fotos[t][k + sin_anden(f["tren"])] = (k, zona, producto, float(f["lat"]), float(f["lon"]), sin_salto(float(f["retraso_min"] or 0)))
    return fotos


def fotos_de_captura(carpeta, prod):
    fotos = {}
    for cp in sorted(glob.glob(f"{carpeta}/cp_*.json")):
        sello = os.path.basename(cp)[3:9]
        try:
            pos, upd, ld = (json.load(open(f"{carpeta}/{p}_{sello}.json")) for p in ("cp", "tu", "ld"))
        except Exception:
            continue
        t = float(pos["header"]["timestamp"]); foto = {}
        ret = {e["tripUpdate"]["trip"]["tripId"]: e["tripUpdate"].get("delay", 0) for e in upd["entity"]}
        for e in pos["entity"]:
            v = e["vehicle"]
            if "position" not in v: continue
            tid = v["trip"]["tripId"]
            foto["c" + sin_anden(v.get("vehicle", {}).get("label", tid))] = ("c", NUCLEOS.get(tid[:2], ""), "", v["position"]["latitude"], v["position"]["longitude"], sin_salto(ret.get(tid, 0) / 60))
        for x in ld["trenes"]:
            foto["l" + x["codComercial"]] = ("l", "", prod.get(str(int(x["codComercial"])), ""), x["latitud"], x["longitud"], float(x.get("ultRetraso") or 0))
        fotos[t] = foto
    return fotos


def km(a, b):
    dy = (a[0] - b[0]) * 111.0; dx = (a[1] - b[1]) * 111.0 * math.cos(math.radians(a[0]))
    return math.hypot(dx, dy)


def rasgos(actual, antes, minutos_tendencia, hora):
    k, zona, producto, lat, lon, d = actual
    if antes:
        tendencia, velocidad, hay = d - antes[5], km((lat, lon), (antes[3], antes[4])) / (minutos_tendencia / 60), 1.0
    else:
        tendencia, velocidad, hay = 0.0, 0.0, 0.0
    return ([d, tendencia, min(velocidad, 320.0), hay, 1.0 if k == "l" else 0.0, math.sin(2 * math.pi * hora / 24), math.cos(2 * math.pi * hora / 24)]
            + [1.0 if zona == z else 0.0 for z in ZONAS] + [1.0 if producto == p else 0.0 for p in PRODUCTOS])


NOMBRES = (["retraso_ahora", "cambio_reciente", "velocidad_kmh", "hay_foto_anterior", "es_larga_distancia", "hora_sen", "hora_cos"]
           + [f"zona_{z}" for z in ZONAS] + [f"producto_{p}" for p in PRODUCTOS])


def ejemplos(fotos, horizonte, tendencia):
    tiempos = sorted(fotos)
    def cerca(t):
        mejor = min(tiempos, key=lambda x: abs(x - t))
        return mejor if abs(mejor - t) <= 90 else None
    X, y, base, grupos = [], [], [], []
    for t in tiempos:
        tf, ta = cerca(t + horizonte * 60), cerca(t - tendencia * 60)
        if tf is None or tf == t: continue
        hora = datetime.datetime.fromtimestamp(t, datetime.timezone(datetime.timedelta(hours=1))).hour
        for id_, actual in fotos[t].items():
            futuro = fotos[tf].get(id_)
            if not futuro: continue
            antes = fotos[ta].get(id_) if ta is not None and ta != t else None
            X.append(rasgos(actual, antes, tendencia, hora)); y.append(futuro[5] - actual[5]); base.append(actual[5]); grupos.append(id_)
    return np.array(X), np.array(y), np.array(base), np.array(grupos)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", nargs="*", default=[]); ap.add_argument("--captura")
    ap.add_argument("--aux", default=os.path.join(os.path.dirname(__file__), "..", "web", "api", "_aux.json"))
    ap.add_argument("--horizonte", type=float, default=30); ap.add_argument("--tendencia", type=float, default=5)
    ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    prod = json.load(open(a.aux))["prod"]
    fotos = fotos_de_captura(a.captura, prod) if a.captura else fotos_de_csv(a.csv, prod)
    X, y, base, grupos = ejemplos(fotos, a.horizonte, a.tendencia)
    print(f"{len(fotos)} fotos, {len(y)} ejemplos, {len(set(grupos))} trenes")
    if len(y) < 500:
        print("todavía hay muy pocos ejemplos para este horizonte; se deja el modelo anterior"); return

    # se separa por tren, para que la prueba sea con trenes que el modelo no ha visto
    entreno, prueba = next(GroupShuffleSplit(n_splits=1, test_size=.25, random_state=7).split(X, y, grupos))
    escala = StandardScaler().fit(X[entreno])
    # los saltos enormes (datos raros de un tren) se recortan para que no dominen el entrenamiento
    red = MLPRegressor(hidden_layer_sizes=(24, 12), activation="relu", alpha=1e-2, learning_rate_init=3e-3,
                       max_iter=600, early_stopping=True, random_state=7).fit(escala.transform(X[entreno]), np.clip(y[entreno], -20, 20))
    # cuánto fiarse de la red frente a «seguirá igual»: se elige con los datos de entreno, nunca con los de prueba
    p_ent = red.predict(escala.transform(X[entreno]))
    confianza = min((0, .25, .5, .75, 1), key=lambda c: np.mean(np.abs(c * p_ent - y[entreno])))
    pred = confianza * red.predict(escala.transform(X[prueba]))
    mae_red = float(np.mean(np.abs(pred - y[prueba])))
    mae_igual = float(np.mean(np.abs(y[prueba])))  # «seguirá igual»: cambio 0
    cambia = np.abs(y[prueba]) >= 2
    print(f"error medio: red {mae_red:.2f} min · seguirá igual {mae_igual:.2f} min")

    # qué mira la red: cuánto empeora el error si se barajan los valores de cada grupo de rasgos (importancia por permutación)
    grupos_rasgos = {"Retraso que lleva ahora": ["retraso_ahora"], "Cómo ha cambiado hace poco": ["cambio_reciente", "hay_foto_anterior"],
                     "Velocidad": ["velocidad_kmh"], "Hora del día": ["hora_sen", "hora_cos"],
                     "Zona": [n for n in NOMBRES if n.startswith("zona_")], "Tipo de tren": ["es_larga_distancia"] + [n for n in NOMBRES if n.startswith("producto_")]}
    rng = np.random.default_rng(7); Xp = X[prueba]; importancia = {}
    for nombre, cols in grupos_rasgos.items():
        idx = [NOMBRES.index(c) for c in cols]; subidas = []
        for _ in range(5):
            Xb = Xp.copy(); orden = rng.permutation(len(Xb)); Xb[:, idx] = Xb[orden][:, idx]
            subidas.append(np.mean(np.abs(confianza * red.predict(escala.transform(Xb)) - y[prueba])) - mae_red)
        importancia[nombre] = round(float(max(0.0, np.mean(subidas))), 3)
    print("importancia:", importancia)

    json.dump({
        "version": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "horizonte_min": a.horizonte, "confianza": confianza, "tendencia_min": a.tendencia,
        "rasgos": NOMBRES, "zonas": ZONAS, "productos": PRODUCTOS,
        "media": escala.mean_.round(5).tolist(), "escala": escala.scale_.round(5).tolist(),
        "capas": [{"w": w.round(5).tolist(), "b": b.round(5).tolist()} for w, b in zip(red.coefs_, red.intercepts_)],
        "importancia": importancia,
        "evaluacion": {
            "fotos": len(fotos), "ejemplos": int(len(y)), "trenes": int(len(set(grupos))), "ejemplos_prueba": int(len(prueba)),
            "error_red_min": round(mae_red, 2), "error_seguira_igual_min": round(mae_igual, 2),
            "error_red_cuando_cambia": round(float(np.mean(np.abs(pred[cambia] - y[prueba][cambia]))), 2) if cambia.any() else None,
            "error_igual_cuando_cambia": round(float(np.mean(np.abs(y[prueba][cambia]))), 2) if cambia.any() else None,
            "porcentaje_que_cambia": round(float(cambia.mean() * 100), 1),
        },
    }, open(a.salida, "w"), ensure_ascii=False)
    print("guardado en", a.salida)


if __name__ == "__main__":
    main()
