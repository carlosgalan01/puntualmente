// Todos los trenes de Renfe en este momento: junta las fuentes abiertas en una sola lista.
// El navegador no puede leerlas directamente (Renfe no lo permite desde otra web), por eso pasa por aquí.
const { nombres, prod } = require("./_aux.json");

const FUENTES = {
  posiciones: "https://gtfsrt.renfe.com/vehicle_positions.json",
  retrasos: "https://gtfsrt.renfe.com/trip_updates.json",
  larga: "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json",
  avisos: "https://gtfsrt.renfe.com/alerts.json",
};

const { NUCLEOS } = require("./_nucleos.js");

// Si una fuente falla, se sirve la última buena (mientras esta instancia siga viva) en vez de dejar el mapa sin esos trenes
const ultimaBuena = {};
async function leer(nombre, url) {
  for (let intento = 0; intento < 2; intento++) {
    try {
      const r = await fetch(url, { signal: AbortSignal.timeout(intento ? 6000 : 4000) });
      if (r.ok) { const j = await r.json(); ultimaBuena[nombre] = { j, t: Date.now() }; return { j, edad: 0 }; }
    } catch {}
  }
  const u = ultimaBuena[nombre];
  return u && Date.now() - u.t < 5 * 60e3 ? { j: u.j, edad: Math.round((Date.now() - u.t) / 1000) } : { j: null, edad: null };
}

const r4 = (v) => Math.round(v * 1e4) / 1e4;
const limpia = (s) => s.replace(/^(#\S+\s*)+/, "").replace(/\s+/g, " ").trim();

module.exports = async (req, res) => {
  const [pos, upd, ld, av] = await Promise.all(Object.entries(FUENTES).map(([n, u]) => leer(n, u)));
  const trenes = [];
  if (pos.j) {
    const retraso = {};
    for (const e of upd.j?.entity ?? []) {
      const tu = e.tripUpdate;
      retraso[tu.trip.tripId] = tu.delay ?? tu.stopTimeUpdate?.[0]?.arrival?.delay ?? 0;
    }
    for (const e of pos.j.entity) {
      const v = e.vehicle;
      if (!v.position) continue;
      const etiqueta = v.vehicle?.label ?? v.trip.tripId;
      const [linea, num] = etiqueta.split("-");
      trenes.push({ id: "c" + etiqueta, k: "c", n: linea, num: num ?? "", z: NUCLEOS[v.trip.tripId.slice(0, 2)] ?? "",
        s: nombres[v.stopId] ?? "", lon: r4(v.position.longitude), lat: r4(v.position.latitude),
        d: Math.round((retraso[v.trip.tripId] ?? 0) / 60) });
    }
  }
  for (const t of ld.j?.trenes ?? []) {
    trenes.push({ id: "l" + t.codComercial, k: "l", n: prod[String(+t.codComercial)] || "Tren", num: t.codComercial,
      o: nombres[t.codOrigen] ?? t.codOrigen, dst: nombres[t.codDestino] ?? t.codDestino, s: nombres[t.codEstSig] ?? "",
      lon: r4(t.longitud), lat: r4(t.latitud), d: +t.ultRetraso || 0 });
  }
  // Avisos oficiales: los más recientes primero, con la zona a la que afectan
  const avisos = (av.j?.entity ?? []).map((e) => {
    const a = e.alert, rutas = a.informedEntity ?? [];
    const zonas = [...new Set(rutas.map((r) => NUCLEOS[(r.routeId ?? "").slice(0, 2)]).filter(Boolean))];
    const lineas = [...new Set(rutas.map((r) => (r.routeId ?? "").trim().match(/(C\d+[a-z]?|R\w+|T\d+|S\d+)$/)?.[1]).filter(Boolean))];
    const texto = a.descriptionText?.translation?.find((x) => x.language === "es")?.text ?? a.descriptionText?.translation?.[0]?.text ?? "";
    return { desde: +(a.activePeriod?.[0]?.start ?? 0), zonas, lineas: lineas.slice(0, 6), texto: limpia(texto) };
  }).filter((a) => a.texto).sort((a, b) => b.desde - a.desde).slice(0, 12);

  res.setHeader("Cache-Control", "s-maxage=10, stale-while-revalidate=20");
  res.status(pos.j || ld.j ? 200 : 502).json({
    t: Math.floor(Date.now() / 1000),
    fuentes: { cercanias: pos.edad, retrasos: upd.edad, larga: ld.edad, avisos: av.edad },
    trenes,
    avisos,
  });
};
