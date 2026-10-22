const form = document.querySelector("#pile-form");
const pile = document.querySelector("#pile");
const readButton = document.querySelector("#read");
const sampleButton = document.querySelector("#sample");
const statusLine = document.querySelector("#status");
const brief = document.querySelector("#brief");
const lineOne = document.querySelector("#line-one");
const lineTwo = document.querySelector("#line-two");
const stamps = document.querySelector("#stamps");
const cards = document.querySelector("#cards");
const historyList = document.querySelector("#history");
const historyEmpty = document.querySelector("#history-empty");

const STAMP = {
  pardon: "Pardoned",
  two_minutes: "Two minutes",
  merge: "Already seen",
};

function setStatus(text, working) {
  statusLine.textContent = text || "";
  statusLine.classList.toggle("working", Boolean(working));
}

function stampWord(verdict) {
  return STAMP[verdict] || "Pardoned";
}

function excerpt(text) {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > 180 ? flat.slice(0, 177) + "…" : flat;
}

function when(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("en", { day: "numeric", month: "short" }).format(date);
}

function renderCards(items) {
  cards.replaceChildren();
  items.forEach((item) => {
    const card = document.createElement("li");
    card.className = "card";

    const copy = document.createElement("div");
    const summary = document.createElement("p");
    summary.className = "summary";
    summary.textContent = item.summary;
    const body = document.createElement("p");
    body.className = "body";
    body.textContent = excerpt(item.body);
    copy.append(summary, body);

    const stamp = document.createElement("p");
    stamp.className = "stamp live";
    stamp.textContent = stampWord(item.verdict);

    card.append(copy, stamp);

    if (item.script) {
      const script = document.createElement("div");
      script.className = "script";
      const reply = document.createElement("p");
      reply.textContent = item.script;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "copy";
      button.textContent = "Copy the reply";
      button.addEventListener("click", async () => {
        await navigator.clipboard.writeText(item.script);
        button.textContent = "Copied";
        setTimeout(() => {
          button.textContent = "Copy the reply";
        }, 1600);
      });
      script.append(reply, button);
      card.append(script);
    }

    cards.append(card);
  });
  stamps.hidden = items.length === 0;
}

function renderHistory(items) {
  historyList.replaceChildren();
  historyEmpty.hidden = items.length > 0;
  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "history-item";
    const stamp = document.createElement("p");
    stamp.className = "stamp";
    stamp.textContent = stampWord(item.verdict);
    const summary = document.createElement("p");
    summary.className = "summary";
    summary.textContent = item.summary;
    const body = document.createElement("p");
    body.className = "body";
    const dated = when(item.created_at);
    body.textContent = dated ? `${dated} · ${excerpt(item.body)}` : excerpt(item.body);
    row.append(stamp, summary, body);
    historyList.append(row);
  });
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history");
    const payload = await response.json();
    if (payload.error) {
      historyEmpty.hidden = false;
      historyEmpty.textContent = payload.error;
      return;
    }
    renderHistory(payload.items || []);
  } catch {
    historyEmpty.hidden = false;
    historyEmpty.textContent = "The pile couldn't be loaded.";
  }
}

async function stampPile(text, seedMemory) {
  readButton.disabled = true;
  sampleButton.disabled = true;
  setStatus("Reading the pile", true);
  brief.hidden = true;
  stamps.hidden = true;

  try {
    const response = await fetch("/api/pile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, seed_memory: seedMemory }),
    });
    if (!response.ok || !response.body) {
      setStatus("The pile didn't go through. Try it again.");
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finished = false;

    while (!finished) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.status) setStatus(event.status, true);
        if (event.error) {
          setStatus(event.error);
          finished = true;
        }
        if (event.done) {
          lineOne.textContent = event.line_one;
          lineTwo.textContent = event.line_two;
          brief.hidden = false;
          renderCards(event.items || []);
          setStatus("");
          finished = true;
          await loadHistory();
        }
      }
      if (done) finished = true;
    }
  } catch {
    setStatus("The pile didn't go through. Is the app still running?");
  } finally {
    readButton.disabled = false;
    sampleButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  stampPile(pile.value, false);
});

sampleButton.addEventListener("click", async () => {
  const response = await fetch("/api/sample");
  const payload = await response.json();
  pile.value = payload.text;
  stampPile(payload.text, true);
});

loadHistory();
