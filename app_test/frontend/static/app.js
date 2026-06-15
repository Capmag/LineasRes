/**
 * App.js — Utilidades modernas para la aplicación
 * - DataTable: búsqueda, ordenamiento, paginación local
 * - LoadingOverlay: indicadores visuales durante requests
 * - apiCall: helper genérico para llamadas con manejo de errores
 *
 * NOTA: este archivo NO modifica el DOM globalmente ni clona elementos.
 * Solo expone clases/funciones reutilizables.
 */

(function (global) {
    'use strict';

    // ============================================================
    // LoadingOverlay - Indicador global de carga
    // ============================================================
    class LoadingOverlay {
        static show(target) {
            const host = target || document.body;
            if (host.querySelector('.app-loading-overlay')) return;

            const overlay = document.createElement('div');
            overlay.className = 'app-loading-overlay';
            overlay.innerHTML = `
                <div class="app-loading-spinner">
                    <div class="spinner-ring"></div>
                </div>
            `;
            host.style.position = host === document.body ? '' : 'relative';
            host.appendChild(overlay);
        }

        static hide(target) {
            const host = target || document.body;
            const overlay = host.querySelector('.app-loading-overlay');
            if (overlay) overlay.remove();
        }

        static wrap(target, asyncFn) {
            return (async () => {
                LoadingOverlay.show(target);
                try {
                    return await asyncFn();
                } finally {
                    LoadingOverlay.hide(target);
                }
            })();
        }
    }

    // ============================================================
    // apiCall - Llamada API con manejo de errores estandarizado
    // Muestra loading overlay automáticamente en `options.loadingTarget`
    // (o en document.body) durante la request.
    // ============================================================
    async function apiCall(url, options = {}) {
        const target = options.loadingTarget || null;
        const showLoading = options.loading !== false;

        if (showLoading) LoadingOverlay.show(target || document.body);

        try {
            const resp = await fetch(url, {
                headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
                ...options,
            });

            let data;
            try {
                data = await resp.json();
            } catch (e) {
                throw new Error(`Respuesta inválida del servidor (HTTP ${resp.status})`);
            }

            if (!resp.ok || data.ok === false) {
                throw new Error(data.msg || `Error HTTP ${resp.status}`);
            }
            return data;
        } finally {
            if (showLoading) LoadingOverlay.hide(target || document.body);
        }
    }

    // ============================================================
    // DataTable - Búsqueda + Ordenamiento + Paginación
    //
    // Uso:
    //   new DataTable({
    //       tableId: 'myTable',     // <table id="myTable">
    //       searchInputId: 'mySearch',
    //       pageSize: 10,            // opcional
    //       paginationId: 'myPag',   // opcional
    //   });
    //
    // El <thead> debe tener data-sort="<tipo>" en cada <th> ordenable.
    // Tipos: "text", "number", "date".
    // ============================================================
    class DataTable {
        constructor(opts) {
            this.table = document.getElementById(opts.tableId);
            if (!this.table) return;
            this.tbody = this.table.querySelector('tbody');
            this.headers = Array.from(this.table.querySelectorAll('thead th'));
            this.allRows = Array.from(this.tbody.querySelectorAll('tr'));

            this.searchInput = opts.searchInputId ? document.getElementById(opts.searchInputId) : null;
            this.pageSize = opts.pageSize || 0; // 0 = sin paginación
            this.pagination = opts.paginationId ? document.getElementById(opts.paginationId) : null;

            this.currentPage = 1;
            this.filteredRows = [...this.allRows];
            this.sortColumn = null;
            this.sortDir = 'asc';

            this.attachSearch();
            this.attachSort();
            this.render();
        }

        attachSearch() {
            if (!this.searchInput) return;
            this.searchInput.addEventListener('input', () => {
                this.applyFilter(this.searchInput.value);
            });
        }

        applyFilter(term) {
            const q = (term || '').trim().toLowerCase();
            if (!q) {
                this.filteredRows = [...this.allRows];
            } else {
                this.filteredRows = this.allRows.filter((row) =>
                    row.textContent.toLowerCase().includes(q)
                );
            }
            this.currentPage = 1;
            this.render();
        }

        attachSort() {
            this.headers.forEach((th, idx) => {
                const type = th.dataset.sort;
                if (!type) return;
                th.classList.add('sortable');
                th.addEventListener('click', () => this.sortBy(idx, type));
            });
        }

        sortBy(colIndex, type) {
            if (this.sortColumn === colIndex) {
                this.sortDir = this.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
                this.sortColumn = colIndex;
                this.sortDir = 'asc';
            }

            const dir = this.sortDir === 'asc' ? 1 : -1;
            this.filteredRows.sort((a, b) => {
                const av = (a.children[colIndex]?.textContent || '').trim();
                const bv = (b.children[colIndex]?.textContent || '').trim();
                let cmp = 0;
                if (type === 'number') {
                    cmp = (parseFloat(av) || 0) - (parseFloat(bv) || 0);
                } else if (type === 'date') {
                    cmp = new Date(av).getTime() - new Date(bv).getTime();
                } else {
                    cmp = av.localeCompare(bv, 'es', { numeric: true });
                }
                return cmp * dir;
            });

            // Update visual indicators
            this.headers.forEach((th, i) => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (i === colIndex) th.classList.add(this.sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
            });

            this.render();
        }

        render() {
            // Hide all rows
            this.allRows.forEach((row) => (row.style.display = 'none'));

            const total = this.filteredRows.length;
            let pageRows = this.filteredRows;

            if (this.pageSize > 0) {
                const start = (this.currentPage - 1) * this.pageSize;
                pageRows = this.filteredRows.slice(start, start + this.pageSize);
            }

            // Reattach rows in correct order
            pageRows.forEach((row) => {
                row.style.display = '';
                this.tbody.appendChild(row);
            });

            // Empty state
            this.toggleEmptyState(total === 0);
            this.renderPagination(total);
        }

        toggleEmptyState(isEmpty) {
            let emptyRow = this.tbody.querySelector('.dt-empty-row');
            if (isEmpty) {
                if (!emptyRow) {
                    emptyRow = document.createElement('tr');
                    emptyRow.className = 'dt-empty-row';
                    const colSpan = this.headers.length || 1;
                    emptyRow.innerHTML = `<td colspan="${colSpan}" class="text-center py-4 text-muted">Sin resultados</td>`;
                    this.tbody.appendChild(emptyRow);
                }
                emptyRow.style.display = '';
            } else if (emptyRow) {
                emptyRow.style.display = 'none';
            }
        }

        renderPagination(total) {
            if (!this.pagination || this.pageSize <= 0) return;
            const totalPages = Math.ceil(total / this.pageSize) || 1;
            if (totalPages <= 1) {
                this.pagination.innerHTML = '';
                return;
            }

            const cp = this.currentPage;
            const pages = [];
            const addBtn = (label, page, disabled, active) => {
                pages.push(`
                    <li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
                        <button type="button" class="page-link" ${disabled ? 'disabled' : ''} data-page="${page}">${label}</button>
                    </li>
                `);
            };

            addBtn('&laquo;', cp - 1, cp === 1, false);
            const start = Math.max(1, cp - 2);
            const end = Math.min(totalPages, cp + 2);
            if (start > 1) {
                addBtn('1', 1, false, cp === 1);
                if (start > 2) pages.push('<li class="page-item disabled"><span class="page-link">…</span></li>');
            }
            for (let p = start; p <= end; p++) {
                addBtn(String(p), p, false, p === cp);
            }
            if (end < totalPages) {
                if (end < totalPages - 1) pages.push('<li class="page-item disabled"><span class="page-link">…</span></li>');
                addBtn(String(totalPages), totalPages, false, cp === totalPages);
            }
            addBtn('&raquo;', cp + 1, cp === totalPages, false);

            this.pagination.innerHTML = `<ul class="pagination">${pages.join('')}</ul>`;
            this.pagination.querySelectorAll('button[data-page]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    const p = parseInt(btn.dataset.page, 10);
                    if (!isNaN(p)) {
                        this.currentPage = p;
                        this.render();
                        this.table.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                });
            });
        }

        /**
         * Quita una fila de la tabla por data-id (sin recargar)
         */
        removeRow(id) {
            const row = this.tbody.querySelector(`tr[data-id="${id}"]`);
            if (!row) return;
            row.remove();
            this.allRows = this.allRows.filter((r) => r !== row);
            this.filteredRows = this.filteredRows.filter((r) => r !== row);
            this.render();
        }
    }

    // ============================================================
    // Autocomplete - Input con dropdown de sugerencias
    //
    // Uso (con endpoint que devuelve [{id, label}, ...]):
    //   const ac = new App.Autocomplete({
    //       input: document.getElementById('directorSearch'),
    //       hidden: document.getElementById('director_id'),
    //       endpoint: '/api/directores',
    //       placeholder: 'Escribe para buscar director...',
    //   });
    //
    // Uso con items locales:
    //   new App.Autocomplete({
    //       input, hidden,
    //       items: [{id: 'A', label: 'Alpha'}, ...],
    //   });
    //
    // El input visible muestra el "label" elegido.
    // El hidden guarda el "id" — eso es lo que se manda al backend.
    // ============================================================
    class Autocomplete {
        constructor(opts) {
            this.input = opts.input;
            this.hidden = opts.hidden;
            this.endpoint = opts.endpoint || null;
            this.items = opts.items || [];
            this.minChars = opts.minChars || 0;
            this.maxResults = opts.maxResults || 50;
            this.onSelect = opts.onSelect || null;

            this.filteredItems = [];
            this.highlightedIdx = -1;
            this.dropdown = null;
            this.suppressBlur = false;

            this.init();
        }

        async init() {
            if (this.endpoint) {
                try {
                    const resp = await fetch(this.endpoint);
                    this.items = await resp.json();
                } catch (e) {
                    console.error('Autocomplete: error cargando endpoint', this.endpoint, e);
                    this.items = [];
                }
            }
            this.buildDropdown();
            this.attachEvents();
        }

        buildDropdown() {
            // Asegurar que el contenedor del input tenga position:relative
            const parent = this.input.parentNode;
            if (getComputedStyle(parent).position === 'static') {
                parent.style.position = 'relative';
            }
            this.dropdown = document.createElement('div');
            this.dropdown.className = 'autocomplete-dropdown';
            this.dropdown.style.display = 'none';
            parent.appendChild(this.dropdown);

            this.input.setAttribute('autocomplete', 'off');
            this.input.setAttribute('spellcheck', 'false');
        }

        attachEvents() {
            this.input.addEventListener('input', () => this.handleInput());
            this.input.addEventListener('focus', () => this.handleFocus());
            this.input.addEventListener('blur', () => {
                // Pequeño delay para permitir click en el dropdown
                setTimeout(() => {
                    if (!this.suppressBlur) this.hide();
                    this.suppressBlur = false;
                }, 150);
            });
            this.input.addEventListener('keydown', (e) => this.handleKeydown(e));

            // Mousedown evita que el blur dispare antes del click
            this.dropdown.addEventListener('mousedown', (e) => {
                this.suppressBlur = true;
            });
        }

        matches(item, query) {
            if (!query) return true;
            const q = query.toLowerCase();
            const label = String(item.label || '').toLowerCase();
            const id = String(item.id || '').toLowerCase();
            return label.includes(q) || id.includes(q);
        }

        handleInput() {
            const value = this.input.value;
            const q = value.trim();

            // Si lo que el usuario escribió NO coincide exactamente con un label/id,
            // limpiar el hidden (todavía no hay selección válida).
            const exact = this.items.find(i =>
                String(i.label || '').toLowerCase() === q.toLowerCase() ||
                String(i.id || '').toLowerCase() === q.toLowerCase()
            );
            this.hidden.value = exact ? exact.id : '';

            // Filtrar
            this.filteredItems = q.length < this.minChars
                ? [...this.items]
                : this.items.filter(i => this.matches(i, q));

            this.highlightedIdx = -1;
            this.render();
            this.show();
        }

        handleFocus() {
            this.filteredItems = [...this.items];
            this.render();
            this.show();
        }

        handleKeydown(e) {
            const visible = this.dropdown.style.display !== 'none';
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                if (!visible) { this.handleFocus(); return; }
                this.highlight(Math.min(this.highlightedIdx + 1, this.filteredItems.length - 1));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.highlight(Math.max(this.highlightedIdx - 1, 0));
            } else if (e.key === 'Enter') {
                if (this.highlightedIdx >= 0 && visible) {
                    e.preventDefault();
                    this.select(this.filteredItems[this.highlightedIdx]);
                }
            } else if (e.key === 'Escape') {
                this.hide();
            }
        }

        render() {
            const visible = this.filteredItems.slice(0, this.maxResults);
            if (visible.length === 0) {
                this.dropdown.innerHTML = '<div class="autocomplete-empty">Sin resultados</div>';
                return;
            }
            this.dropdown.innerHTML = visible.map((item, idx) => `
                <div class="autocomplete-item ${idx === this.highlightedIdx ? 'highlighted' : ''}" data-idx="${idx}">
                    <span class="ac-label">${this.escape(item.label)}</span>
                    <span class="ac-id">${this.escape(item.id)}</span>
                </div>
            `).join('');

            this.dropdown.querySelectorAll('.autocomplete-item').forEach((el) => {
                const idx = parseInt(el.dataset.idx, 10);
                el.addEventListener('click', () => this.select(this.filteredItems[idx]));
                el.addEventListener('mouseenter', () => this.highlight(idx));
            });
        }

        highlight(idx) {
            this.highlightedIdx = idx;
            this.dropdown.querySelectorAll('.autocomplete-item').forEach((el, i) => {
                el.classList.toggle('highlighted', i === idx);
            });
            const target = this.dropdown.querySelector('.autocomplete-item.highlighted');
            if (target) target.scrollIntoView({ block: 'nearest' });
        }

        select(item) {
            if (!item) return;
            this.input.value = item.label;
            this.hidden.value = item.id;
            this.hide();
            if (this.onSelect) this.onSelect(item);
        }

        show() {
            this.dropdown.style.display = 'block';
        }

        hide() {
            this.dropdown.style.display = 'none';
            this.highlightedIdx = -1;
        }

        setValue(id, label) {
            this.input.value = label || '';
            this.hidden.value = id || '';
        }

        clear() {
            this.input.value = '';
            this.hidden.value = '';
        }

        escape(str) {
            return String(str ?? '').replace(/[&<>"']/g, (c) => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            }[c]));
        }
    }

    // ============================================================
    // Modal safety net
    //
    // Si una navegación rápida o un error JS deja un modal "abierto"
    // (backdrop, body.modal-open, overflow:hidden), la página queda
    // bloqueada y nada es clickeable. Esto limpia ese estado al cargar.
    // ============================================================
    function cleanupStuckModalState() {
        // Quitar backdrops huérfanos
        document.querySelectorAll('.modal-backdrop').forEach((el) => el.remove());

        // Quitar clases/estilos que Bootstrap añade al body
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';

        // Forzar que cualquier modal sin .show no tenga display inline
        document.querySelectorAll('.modal').forEach((modal) => {
            if (!modal.classList.contains('show')) {
                modal.style.display = '';
                modal.setAttribute('aria-hidden', 'true');
                modal.removeAttribute('aria-modal');
                modal.removeAttribute('role');
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', cleanupStuckModalState);
    } else {
        cleanupStuckModalState();
    }

    // También al volver con back/forward del navegador
    window.addEventListener('pageshow', cleanupStuckModalState);

    // ============================================================
    // Expose
    // ============================================================
    global.App = {
        DataTable,
        LoadingOverlay,
        Autocomplete,
        apiCall,
        cleanupStuckModalState,
    };
})(window);
