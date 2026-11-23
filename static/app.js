const listEl = document.getElementById("people");
const sortEl = document.getElementById("sort");
const groupFilterEl = document.getElementById("group-filter");
const form = document.getElementById("add-form");
const formMsg = document.getElementById("form-msg");

async function loadGroups() {
  const groups = await fetch("/api/groups").then((r) => r.json());

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a group";
  form.group.appendChild(placeholder);

  for (const g of groups) {
    for (const select of [form.group, groupFilterEl]) {
      const opt = document.createElement("option");
      opt.value = g;
      opt.textContent = g;
      select.appendChild(opt);
    }
  }
}

function timeAgo(sqliteTs) {
  if (!sqliteTs) return null;
  const then = new Date(sqliteTs.replace(" ", "T") + "Z");
  const secs = Math.floor((Date.now() - then.getTime()) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins} minute${mins === 1 ? "" : "s"} ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days} day${days === 1 ? "" : "s"} ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `${weeks} week${weeks === 1 ? "" : "s"} ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months} month${months === 1 ? "" : "s"} ago`;
  const years = Math.floor(days / 365);
  return `${years} year${years === 1 ? "" : "s"} ago`;
}

async function fetchPeople() {
  const params = new URLSearchParams({ sort: sortEl.value });
  if (groupFilterEl.value) params.set("group", groupFilterEl.value);
  const res = await fetch(`/api/people?${params}`);
  return res.json();
}

function personCard(p, rank) {
  const card = document.createElement("div");
  card.className = "person";
  card.dataset.id = p.id;

  const pct = p.total > 0
    ? Math.round((p.helpful / p.total) * 100)
    : null;

  card.innerHTML = `
    <div class="rank">#${rank}</div>
    <div class="person-main">
      <p class="person-name"></p>
      <p class="person-title"></p>
      <p class="person-group"></p>
      <p class="person-email"></p>
    </div>
    <div class="person-right">
      <div class="stats">
        <span class="score-line">score ${p.score.toFixed(2)}</span>
        <span>${p.helpful} helpful / ${p.no_response} no response (${p.total} vote${p.total === 1 ? "" : "s"})</span>
        ${pct !== null ? `<span>${pct}% quick response</span>` : "<span>no votes yet</span>"}
        <span class="recency"></span>
      </div>
      <div class="vote-btns">
        <button class="vote-btn helpful-btn ${p.your_vote === "helpful" ? "selected" : ""}"
                data-type="helpful" title="Responds immediately">Helpful</button>
        <button class="vote-btn noresponse-btn ${p.your_vote === "no_response" ? "selected" : ""}"
                data-type="no_response" title="No response to emails">No response</button>
      </div>
    </div>
  `;

  card.querySelector(".person-name").textContent = p.name;
  card.querySelector(".person-title").textContent = p.title;
  card.querySelector(".person-group").textContent = p.grp || "Group: (none)";
  card.querySelector(".person-email").textContent = p.email;

  const recencyEl = card.querySelector(".recency");
  const lastHelpful = timeAgo(p.last_helpful);
  const lastNoResponse = timeAgo(p.last_no_response);
  if (p.total > 0) {
    recencyEl.textContent =
      `last helpful: ${lastHelpful || "never"} / ` +
      `last no response: ${lastNoResponse || "never"}`;
  }

  card.querySelectorAll(".vote-btn").forEach((btn) => {
    btn.addEventListener("click", () => castVote(p.id, btn.dataset.type));
  });

  return card;
}

async function render() {
  const people = await fetchPeople();
  listEl.innerHTML = "";

  if (!Array.isArray(people) || people.length === 0) {
    listEl.innerHTML = '<p class="empty">No contacts yet. Add the first one above.</p>';
    return;
  }

  people.forEach((p, i) => listEl.appendChild(personCard(p, i + 1)));
}

async function castVote(personId, type) {
  const res = await fetch(`/api/people/${personId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type }),
  });
  if (res.ok) {
    render();
  } else {
    alert("Vote failed. Please try again.");
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formMsg.textContent = "";
  formMsg.className = "form-msg";

  const res = await fetch("/api/people", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: form.name.value,
      title: form.title.value,
      email: form.email.value,
      group: form.group.value,
    }),
  });

  if (res.ok) {
    form.reset();
    formMsg.textContent = "Contact added.";
    formMsg.classList.add("ok");
    render();
  } else {
    const body = await res.json().catch(() => ({}));
    formMsg.textContent = body.error || "Could not add contact.";
    formMsg.classList.add("error");
  }
});

sortEl.addEventListener("change", render);
groupFilterEl.addEventListener("change", render);
loadGroups();
render();
