// Todos los trenes de Renfe en este momento: junta las tres fuentes abiertas en una sola lista.
// El navegador no puede leerlas directamente (Renfe no lo permite desde otra web), por eso pasa por aquí.
const { nombres, prod } = require("./_aux.json");

const FUENTES = {
  posiciones: "https://gtfsrt.renfe.com/vehicle_positions.json",
  retrasos: "https://gtfsrt.renfe.com/trip_updates.json",
  larga: "https://tiempo-real.largorecorrido.renfe.com/renfe-visor/flotaLD.json",
};

const leer = (url) => fetch(url, { signal: AbortSignal.timeout(8000) }).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const r4 = (v) => Math.round(v * 1e4) / 1e4;

module.exports = async (req, res) => {
  const [pos, upd, ld] = await Promise.all(Object.values(FUENTES).map(leer));
  const trenes = [];
  if (pos) {
    const retraso = {};
    for (const e of upd?.entity ?? []) {
      const tu = e.tripUpdate;
      retraso[tu.trip.tripId] = tu.delay ?? tu.stopTimeUpdate?.[0]?.arrival?.delay ?? 0;
    }
    for (const e of pos.entity) {
      const v = e.vehicle;
      if (!v.position) continue;
      const etiqueta = v.vehicle?.label ?? v.trip.tripId;
      const [linea, num] = etiqueta.split("-");
      trenes.push({ id: "c" + etiqueta, k: "c", n: linea, num: num ?? "", s: nombres[v.stopId] ?? "",
        lon: r4(v.position.longitude), lat: r4(v.position.latitude), d: Math.round((retraso[v.trip.tripId] ?? 0) / 60) });
    }
  }
  for (const t of ld?.trenes ?? []) {
    trenes.push({ id: "l" + t.codComercial, k: "l", n: prod[String(+t.codComercial)] || "Tren", num: t.codComercial,
      o: nombres[t.codOrigen] ?? t.codOrigen, dst: nombres[t.codDestino] ?? t.codDestino, s: nombres[t.codEstSig] ?? "",
      lon: r4(t.longitud), lat: r4(t.latitud), d: +t.ultRetraso || 0 });
  }
  res.setHeader("Cache-Control", "s-maxage=10, stale-while-revalidate=20");
  res.status(pos || ld ? 200 : 502).json({
    t: Math.floor(Date.now() / 1000),
    fuentes: { cercanias: !!pos, retrasos: !!upd, larga: !!ld },
    trenes,
  });
};
