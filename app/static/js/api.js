// Schreibende Aufrufe an /api/... immer mit Kennung X-Hoerste: 1 (CSRF-Schutz).

export async function sende(url, daten = {}) {
  const antwort = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-Hoerste": "1" },
    body: JSON.stringify(daten),
  });
  let inhalt = {};
  try {
    inhalt = await antwort.json();
  } catch (_) {
    // keine JSON-Antwort
  }
  if (!antwort.ok) {
    let text = inhalt.detail;
    if (Array.isArray(text)) text = "Bitte die Eingaben prüfen.";
    if (antwort.status === 401 && !text) text = "Bitte zuerst anmelden.";
    throw new Error(text || `Fehler ${antwort.status}`);
  }
  return inhalt;
}
