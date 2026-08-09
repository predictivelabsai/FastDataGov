function toggleNav() {
  document.body.classList.toggle("nav-open");
}

function drawLineage() {
  const graph = document.getElementById("lineage-graph");
  if (!graph) return;
  const svg = graph.querySelector(".lineage-svg");
  const bounds = graph.getBoundingClientRect();
  svg.setAttribute("viewBox", `0 0 ${bounds.width} ${bounds.height}`);
  svg.innerHTML = "";

  graph.querySelectorAll(".lineage-edge-data").forEach((edge) => {
    const source = graph.querySelector(`.lineage-node[data-id="${edge.dataset.source}"]`);
    const target = graph.querySelector(`.lineage-node[data-id="${edge.dataset.target}"]`);
    if (!source || !target) return;
    const from = source.getBoundingClientRect();
    const to = target.getBoundingClientRect();
    const x1 = from.right - bounds.left;
    const y1 = from.top + from.height / 2 - bounds.top;
    const x2 = to.left - bounds.left;
    const y2 = to.top + to.height / 2 - bounds.top;
    const bend = Math.max(35, Math.abs(x2 - x1) * 0.42);
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
    path.setAttribute("class", `lineage-path ${edge.dataset.evidence}`);
    const title = document.createElementNS("http://www.w3.org/2000/svg", "title");
    title.textContent = `${edge.dataset.label} · ${edge.dataset.evidence.replace("_", " ")}`;
    path.appendChild(title);
    svg.appendChild(path);
  });
}

document.addEventListener("DOMContentLoaded", drawLineage);
window.addEventListener("resize", () => window.requestAnimationFrame(drawLineage));

document.addEventListener("click", (event) => {
  if (event.target.closest('[data-action="toggle-nav"]')) toggleNav();
});

// The app uses one deliberately small hypermedia behavior. Forms remain fully
// functional without JavaScript; when hx-post is present, replace the declared
// target with the server-rendered fragment and keep focus in the work queue.
document.addEventListener("submit", async (event) => {
  const form = event.target.closest("form[hx-post]");
  if (!form) return;
  event.preventDefault();
  const target = document.querySelector(form.getAttribute("hx-target"));
  if (!target) return form.submit();
  const response = await fetch(form.getAttribute("hx-post"), {
    method: "POST",
    headers: { "HX-Request": "true" },
    body: new FormData(form),
    credentials: "same-origin",
  });
  if (!response.ok) return;
  const template = document.createElement("template");
  template.innerHTML = (await response.text()).trim();
  target.replaceWith(template.content.firstElementChild);
});
