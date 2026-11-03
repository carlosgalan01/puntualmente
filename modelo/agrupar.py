"""Familias de líneas: agrupa las líneas de Cercanías por cómo se comportan (k-medias).

Para cada línea calcula, sobre todas las fotos: retraso medio, cuánto varía, qué parte de sus trenes
pasa de 15 minutos y si ha ido a peor del principio al final. Agrupa con k-medias y nombra cada grupo
por su retraso medio. Exporta el resultado para la web.

Uso:  python agrupar.py --csv datos/*.csv --salida web/base/familias.json
      python agrupar.py --captura carpeta --salida ...
"""
import argparse, datetime, json, os
from collections import defaultdict

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from entrenar import fotos_de_captura, fotos_de_csv

NOMBRES = ["Van en hora", "Retraso leve", "Retraso alto", "Muy mal"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", nargs="*", default=[]); ap.add_argument("--captura")
    ap.add_argument("--aux", default=os.path.join(os.path.dirname(__file__), "..", "web", "api", "_aux.json"))
    ap.add_argument("--grupos", type=int, default=4); ap.add_argument("--salida", required=True)
    a = ap.parse_args()
    prod = json.load(open(a.aux))["prod"]
    fotos = fotos_de_captura(a.captura, prod) if a.captura else fotos_de_csv(a.csv, prod)
    tiempos = sorted(fotos)
    por_linea = defaultdict(list)  # línea -> [(t, retraso)]
    for t in tiempos:
        for id_, (k, zona, _, _, _, d) in fotos[t].items():
            if k == "c" and zona:
                por_linea[f"{id_[1:].split('-')[0]} {zona}"].append((t, d))
    lineas, X = [], []
    mitad = tiempos[len(tiempos) // 2] if tiempos else 0
    for linea, obs in por_linea.items():
        if len(obs) < 10: continue
        d = np.array([o[1] for o in obs])
        antes = [o[1] for o in obs if o[0] < mitad] or [0]; despues = [o[1] for o in obs if o[0] >= mitad] or [0]
        rasgos = [d.mean(), d.std(), (d > 15).mean() * 100, np.mean(despues) - np.mean(antes)]
        lineas.append(linea); X.append(rasgos)
    if len(lineas) < 20:
        print(f"sólo {len(lineas)} líneas con datos suficientes; se dejan las familias anteriores"); return
    X = np.array(X)
    km = KMeans(n_clusters=a.grupos, n_init=20, random_state=7).fit(StandardScaler().fit_transform(X))
    # el nombre de cada grupo sale de su retraso medio: el que menos, «Van en hora»; el que más, «Muy mal»
    orden = np.argsort([X[km.labels_ == g, 0].mean() for g in range(a.grupos)])
    rango = {g: int(np.where(orden == g)[0][0]) for g in range(a.grupos)}
    familias = [{"nombre": NOMBRES[r], "rango": r,
                 "lineas": int((km.labels_ == g).sum()),
                 "retraso_medio": round(float(X[km.labels_ == g, 0].mean()), 1),
                 "graves_pct": round(float(X[km.labels_ == g, 2].mean()), 1)} for g, r in sorted(rango.items(), key=lambda x: x[1])]
    puntos = [{"linea": l, "familia": rango[int(g)], "retraso_medio": round(float(x[0]), 1), "variacion": round(float(x[1]), 1),
               "graves_pct": round(float(x[2]), 1), "cambio": round(float(x[3]), 1)} for l, x, g in zip(lineas, X, km.labels_)]
    json.dump({"version": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "fotos": len(tiempos),
               "familias": familias, "lineas": puntos}, open(a.salida, "w"), ensure_ascii=False)
    for f in familias: print(f)
    print(len(puntos), "líneas agrupadas ->", a.salida)


if __name__ == "__main__":
    main()
