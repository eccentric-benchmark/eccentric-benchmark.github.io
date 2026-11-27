// ECCentric site: small enhancements shared by every page. Everything here is optional; the pages work without it.
(function () {
    // Pipeline diagram: the list of each stage opens on hover or focus, and with the toggle on touch screens
    document.querySelectorAll(".stage").forEach(function (stage) {
        var button = stage.querySelector(".stage-toggle");
        if (!button) return;
        button.hidden = false;
        button.addEventListener("click", function (e) {
            e.preventDefault();
            var open = !stage.classList.contains("open");
            document.querySelectorAll(".stage.open").forEach(function (s) {
                s.classList.remove("open");
                s.querySelector(".stage-toggle").setAttribute("aria-expanded", "false");
            });
            stage.classList.toggle("open", open);
            button.setAttribute("aria-expanded", String(open));
        });
    });
    document.addEventListener("keydown", function (e) {
        if (e.key !== "Escape") return;
        document.querySelectorAll(".stage.open").forEach(function (s) {
            s.classList.remove("open");
            s.querySelector(".stage-toggle").setAttribute("aria-expanded", "false");
        });
        if (document.activeElement && document.activeElement.closest(".stage")) document.activeElement.blur();
    });
    document.addEventListener("click", function (e) {
        if (e.target.closest(".stage")) return;
        document.querySelectorAll(".stage.open").forEach(function (s) {
            s.classList.remove("open");
            s.querySelector(".stage-toggle").setAttribute("aria-expanded", "false");
        });
    });

    // Sortable tables: a header with data-sort sorts by its column; cells may carry data-value for the sort key
    document.querySelectorAll("table.data").forEach(function (table) {
        var heads = table.querySelectorAll("thead th[data-sort]");
        heads.forEach(function (th) {
            th.tabIndex = 0;
            function sort() {
                var index = Array.prototype.indexOf.call(th.parentNode.children, th);
                var numeric = th.dataset.sort === "num";
                var dir = th.getAttribute("aria-sort") === "descending" ? 1 : (th.getAttribute("aria-sort") === "ascending" ? -1 : (numeric ? -1 : 1));
                heads.forEach(function (h) { h.removeAttribute("aria-sort"); });
                th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
                var body = table.tBodies[0];
                var rows = Array.prototype.slice.call(body.rows);
                rows.sort(function (a, b) {
                    var x = a.cells[index], y = b.cells[index];
                    var vx = x.dataset.value !== undefined ? x.dataset.value : x.textContent.trim();
                    var vy = y.dataset.value !== undefined ? y.dataset.value : y.textContent.trim();
                    if (numeric) {
                        vx = vx === "" ? NaN : parseFloat(vx); vy = vy === "" ? NaN : parseFloat(vy);
                        if (isNaN(vx)) return 1;
                        if (isNaN(vy)) return -1;
                        return dir * (vx - vy);
                    }
                    return dir * vx.localeCompare(vy, undefined, { numeric: true });
                });
                rows.forEach(function (r) { body.appendChild(r); });
            }
            th.addEventListener("click", sort);
            th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
        });
    });

    // Copy buttons for code blocks (BibTeX)
    document.querySelectorAll(".copy-wrap").forEach(function (wrap) {
        var pre = wrap.querySelector("pre");
        if (!pre || !navigator.clipboard) return;
        var button = document.createElement("button");
        button.type = "button";
        button.className = "copy";
        button.textContent = "Copy";
        button.addEventListener("click", function () {
            navigator.clipboard.writeText(pre.textContent).then(function () {
                button.textContent = "Copied";
                setTimeout(function () { button.textContent = "Copy"; }, 1600);
            });
        });
        wrap.appendChild(button);
    });
})();

// Homepage panel: hovering or focusing a cell previews its experiment; clicking (or Enter) keeps it.
// Arrow keys move between cells.
(function () {
    var panel = document.getElementById("lerpanel");
    if (!panel) return;
    var data;
    try { data = JSON.parse(document.getElementById("lp-data").textContent); } catch (e) { return; }
    var detail = panel.querySelector(".lp-detail");
    var cells = Array.prototype.slice.call(panel.querySelectorAll(".lp-cell"));
    var selected = panel.querySelector('.lp-cell[aria-pressed="true"]') || cells[0];
    function mark(cell) {
        panel.querySelectorAll("th.on").forEach(function (th) { th.classList.remove("on"); });
        if (!cell) return;
        var row = panel.querySelector('tbody th[data-row="' + cell.dataset.row + '"]');
        var col = panel.querySelector('thead th[data-col="' + cell.dataset.col + '"]');
        if (row) row.classList.add("on");
        if (col) col.classList.add("on");
    }
    function show(cell) { detail.innerHTML = data[+cell.dataset.k]; mark(cell); }
    function select(cell) {
        if (selected) { selected.setAttribute("aria-pressed", "false"); selected.tabIndex = -1; }
        selected = cell;
        cell.setAttribute("aria-pressed", "true");
        cell.tabIndex = 0;
        show(cell);
    }
    mark(selected);
    cells.forEach(function (cell) {
        cell.addEventListener("click", function () { select(cell); });
        cell.addEventListener("mouseenter", function () { show(cell); });
        cell.addEventListener("focus", function () { show(cell); });
    });
    panel.querySelector(".lp-grid").addEventListener("mouseleave", function () { if (selected) show(selected); });
    panel.querySelector(".lp-grid").addEventListener("focusout", function (e) {
        if (!panel.querySelector(".lp-grid").contains(e.relatedTarget) && selected) show(selected);
    });
    panel.addEventListener("keydown", function (e) {
        var cell = e.target.closest && e.target.closest(".lp-cell");
        if (!cell) return;
        var moves = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
        var m = moves[e.key];
        if (!m) return;
        e.preventDefault();
        var r = +cell.dataset.row, c = +cell.dataset.col, next = null;
        for (var step = 1; step < 30 && !next; step++) {
            next = panel.querySelector('.lp-cell[data-row="' + (r + m[0] * step) + '"][data-col="' + (c + m[1] * step) + '"]');
            if (r + m[0] * step < 0 || c + m[1] * step < 0) break;
        }
        if (next) { select(next); next.focus(); }
    });
})();
