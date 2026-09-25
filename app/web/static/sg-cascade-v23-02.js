(() => {
  const list = document.querySelector("[data-cascade-priority-list]");
  const input = document.querySelector("[data-cascade-priority-input]");
  if (!(list instanceof HTMLElement) || !(input instanceof HTMLInputElement)) return;

  const items = () => Array.from(list.querySelectorAll("[data-priority-channel]"));

  const sync = () => {
    const rows = items();
    rows.forEach((row, index) => {
      const rank = row.querySelector(".cs-priority-rank");
      if (rank) rank.textContent = String(index + 1);
    });
    input.value = rows.map(row => row.dataset.priorityChannel || "").filter(Boolean).join(", ");
  };

  const move = (row, direction) => {
    if (!(row instanceof HTMLElement)) return;
    if (direction === "up" && row.previousElementSibling) {
      list.insertBefore(row, row.previousElementSibling);
    } else if (direction === "down" && row.nextElementSibling) {
      list.insertBefore(row.nextElementSibling, row);
    }
    sync();
  };

  list.addEventListener("click", event => {
    const button = event.target instanceof Element ? event.target.closest("[data-priority-move]") : null;
    if (!(button instanceof HTMLButtonElement)) return;
    const row = button.closest("[data-priority-channel]");
    move(row, button.dataset.priorityMove || "");
  });

  let dragged = null;
  list.addEventListener("dragstart", event => {
    const row = event.target instanceof Element ? event.target.closest("[data-priority-channel]") : null;
    if (!(row instanceof HTMLElement)) return;
    dragged = row;
    row.classList.add("dragging");
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = "move";
      event.dataTransfer.setData("text/plain", row.dataset.priorityChannel || "");
    }
  });

  list.addEventListener("dragover", event => {
    if (!(dragged instanceof HTMLElement)) return;
    event.preventDefault();
    const target = event.target instanceof Element ? event.target.closest("[data-priority-channel]") : null;
    if (!(target instanceof HTMLElement) || target === dragged) return;
    const rect = target.getBoundingClientRect();
    const after = event.clientY > rect.top + rect.height / 2;
    list.insertBefore(dragged, after ? target.nextElementSibling : target);
  });

  list.addEventListener("dragend", () => {
    if (dragged instanceof HTMLElement) dragged.classList.remove("dragging");
    dragged = null;
    sync();
  });

  sync();
})();
