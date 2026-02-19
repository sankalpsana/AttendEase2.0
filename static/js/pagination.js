/**
 * TablePaginator - Reusable client-side pagination for dynamically populated tables.
 *
 * Usage:
 *   const paginator = new TablePaginator({
 *       tbodyId: 'studentTableBody',
 *       paginationContainerId: 'studentPagination',
 *       rowsPerPage: 10,
 *       searchInputId: 'searchStudent' // optional
 *   });
 *   // After populating <tbody>, call:
 *   paginator.init();
 */
class TablePaginator {
    constructor(options) {
        this.tbody = document.getElementById(options.tbodyId);
        this.container = document.getElementById(options.paginationContainerId);
        this.rowsPerPage = options.rowsPerPage || 10;
        this.currentPage = 1;
        this.searchInput = options.searchInputId ? document.getElementById(options.searchInputId) : null;

        if (this.searchInput) {
            this.searchInput.addEventListener('input', () => {
                this.currentPage = 1;
                this.render();
            });
        }
    }

    getVisibleRows() {
        const rows = Array.from(this.tbody.querySelectorAll('tr'));
        if (!this.searchInput) return rows;

        const query = this.searchInput.value.toLowerCase();
        if (!query) return rows;

        return rows.filter(row => row.innerText.toLowerCase().includes(query));
    }

    getTotalPages(visibleRows) {
        return Math.max(1, Math.ceil(visibleRows.length / this.rowsPerPage));
    }

    init() {
        this.currentPage = 1;
        this.render();
    }

    render() {
        const allRows = Array.from(this.tbody.querySelectorAll('tr'));
        const searchQuery = this.searchInput ? this.searchInput.value.toLowerCase() : '';

        // First, filter by search
        let visibleRows = allRows;
        if (searchQuery) {
            visibleRows = allRows.filter(row => row.innerText.toLowerCase().includes(searchQuery));
        }

        const totalPages = this.getTotalPages(visibleRows);
        if (this.currentPage > totalPages) this.currentPage = totalPages;

        const start = (this.currentPage - 1) * this.rowsPerPage;
        const end = start + this.rowsPerPage;

        // Hide all rows first
        allRows.forEach(row => row.style.display = 'none');

        // Show only current page rows from filtered set
        visibleRows.forEach((row, idx) => {
            row.style.display = (idx >= start && idx < end) ? '' : 'none';
        });

        this.renderControls(visibleRows.length, totalPages);
    }

    renderControls(totalItems, totalPages) {
        if (!this.container) return;

        const start = (this.currentPage - 1) * this.rowsPerPage + 1;
        const end = Math.min(this.currentPage * this.rowsPerPage, totalItems);

        let html = `
            <div class="pagination-wrapper">
                <div class="pagination-info">
                    Showing <strong>${totalItems > 0 ? start : 0}–${end}</strong> of <strong>${totalItems}</strong> entries
                </div>
                <nav>
                    <ul class="pagination pagination-sm mb-0">`;

        // Previous button
        html += `<li class="page-item ${this.currentPage === 1 ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${this.currentPage - 1}">&laquo;</a>
                 </li>`;

        // Page numbers (show max 5 around current)
        let startPage = Math.max(1, this.currentPage - 2);
        let endPage = Math.min(totalPages, startPage + 4);
        if (endPage - startPage < 4) startPage = Math.max(1, endPage - 4);

        for (let i = startPage; i <= endPage; i++) {
            html += `<li class="page-item ${i === this.currentPage ? 'active' : ''}">
                        <a class="page-link" href="#" data-page="${i}">${i}</a>
                     </li>`;
        }

        // Next button
        html += `<li class="page-item ${this.currentPage === totalPages ? 'disabled' : ''}">
                    <a class="page-link" href="#" data-page="${this.currentPage + 1}">&raquo;</a>
                 </li>`;

        html += `</ul></nav></div>`;

        this.container.innerHTML = html;

        // Bind click events
        this.container.querySelectorAll('.page-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const page = parseInt(e.target.dataset.page);
                if (page >= 1 && page <= totalPages) {
                    this.currentPage = page;
                    this.render();
                }
            });
        });
    }
}
