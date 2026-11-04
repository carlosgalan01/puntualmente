// «Hoy a cámara rápida»: lee lo que la caja negra ha grabado un día y lo devuelve tren a tren, foto a foto.
const { nombres, prod } = require("./_aux.json");
const { NUCLEOS } = require("./_nucleos.js");

const RAW = "https://raw.githubusercontent.com/carlosgalan01/puntualmente/datos/datos/";
const r3 = (v) => Math.round(v * 1e3) / 1e3;

module.exports = async (req, res) => {
  const dia = /^\d{4}-\d{2}-\d{2}$/.test(req.query?.dia ?? "") ? req.query.dia : new Date().toISOString().slice(0, 10);
  const r = await fetch(RAW + dia + ".csv", { signal: AbortSignal.timeout(9000) }).catch(() => null);
  if (!r?.ok) return res.status(404).json({ dia, t: [], trenes: [] });
  const filas = (await r.text()).trim().split("\n").slice(1);
  const fotos = new Map(), trenes = new Map();
  for (const f of filas) {
    const [foto, tipo, tren0, lat, lon, ret, sig, extra] = f.split(",");
    // el mismo tren lleva «-PLATF.(n)» mientras está en un andén: se quita para no partirlo en dos
    const tren = tren0.replace(/-PLATF\.\(.*\)$/, "");
    if (!fotos.has(foto)) fotos.set(foto, fotos.size);
    const i = fotos.get(foto), k = tipo === "larga" ? "l" : "c", id = k + tren;
    let t = trenes.get(id);
    if (!t) {
      if (k === "l") {
        const [od, p] = (extra ?? "").split("|"), [o, d] = od.split(">");
        t = { id, k, n: prod[String(+tren)] || "Tren", num: tren, o: nombres[o] ?? o, dst: nombres[d] ?? d, p: [] };
      } else {
        const trip = (extra ?? "").split("|")[1] ?? "", [n, num] = tren.split("-");
        t = { id, k, n, num: num ?? "", z: NUCLEOS[trip.slice(0, 2)] ?? "", p: [] };
      }
      trenes.set(id, t);
    }
    t.s = nombres[sig] ?? t.s ?? "";
    t.p.push([i, r3(+lon), r3(+lat), +ret || 0]);
  }
  res.setHeader("Cache-Control", "s-maxage=240, stale-while-revalidate=600");
  res.json({ dia, t: [...fotos.keys()].map((f) => Math.floor(Date.parse(f) / 1000)), trenes: [...trenes.values()] });
};
