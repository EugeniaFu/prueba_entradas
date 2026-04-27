document.addEventListener("DOMContentLoaded", function () {
    
    // Buscar tabla de rentas, cotizaciones o clientes
    const tablaRentas = document.getElementById("tablaRentas");
    const tablaCotizaciones = document.getElementById("tablaCotizaciones");
    const tablaClientes = document.getElementById("tablaClientes");
    const table = tablaRentas || tablaCotizaciones || tablaClientes;
    
    if (!table) return; // Si no hay ninguna tabla, salir
    
    // Definir filas por página según la tabla
    let rowsPerPage;
    if (tablaClientes) {
        rowsPerPage = 15; // 10 clientes por página
    } else {
        rowsPerPage = 10; // 8 rentas/cotizaciones por página
    }
    
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const paginationContainer = document.getElementById("pagination-container");
    
    if (!paginationContainer) return;

    const SIBLINGS = 1; // Cantidad de paginas vecinas al numero actual

    function buildCompactPages(currentPage, totalPages) {
      if (totalPages <= 7) {
        return Array.from({ length: totalPages }, (_, i) => i + 1);
      }

      const pages = [1];
      const left = Math.max(2, currentPage - SIBLINGS);
      const right = Math.min(totalPages - 1, currentPage + SIBLINGS);

      if (left > 2) pages.push("...");

      for (let p = left; p <= right; p++) {
        pages.push(p);
      }

      if (right < totalPages - 1) pages.push("...");
      pages.push(totalPages);

      return pages;
    }

    function renderPagination(currentPage, totalPages, onPageChange) {
      paginationContainer.innerHTML = "";

      if (totalPages <= 1) return;

      const ul = document.createElement("ul");
      ul.className = "pagination";

      const prevBtn = document.createElement("li");
      prevBtn.className = `page-item ${currentPage === 1 ? "disabled" : ""}`;
      prevBtn.innerHTML = '<a class="page-link" href="#">&laquo;</a>';
      prevBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (currentPage > 1) onPageChange(currentPage - 1);
      });
      ul.appendChild(prevBtn);

      const compactPages = buildCompactPages(currentPage, totalPages);
      compactPages.forEach((page) => {
        const li = document.createElement("li");

        if (page === "...") {
          li.className = "page-item disabled";
          li.innerHTML = '<span class="page-link">&hellip;</span>';
        } else {
          li.className = `page-item ${page === currentPage ? "active" : ""}`;
          li.innerHTML = `<a class="page-link" href="#">${page}</a>`;
          li.addEventListener("click", (e) => {
            e.preventDefault();
            onPageChange(page);
          });
        }

        ul.appendChild(li);
      });

      const nextBtn = document.createElement("li");
      nextBtn.className = `page-item ${currentPage === totalPages ? "disabled" : ""}`;
      nextBtn.innerHTML = '<a class="page-link" href="#">&raquo;</a>';
      nextBtn.addEventListener("click", (e) => {
        e.preventDefault();
        if (currentPage < totalPages) onPageChange(currentPage + 1);
      });
      ul.appendChild(nextBtn);

      paginationContainer.appendChild(ul);
    }

    function showPage(page) {
      const totalPages = Math.ceil(rows.length / rowsPerPage);
      if (totalPages <= 0) return;

      const safePage = Math.max(1, Math.min(page, totalPages));
      const start = (safePage - 1) * rowsPerPage;
      const end = start + rowsPerPage;

      rows.forEach((row, i) => {
        row.style.display = i >= start && i < end ? "" : "none";
      });

      renderPagination(safePage, totalPages, showPage);
    }

    if (rows.length > rowsPerPage) {
      showPage(1);
    }
    
    // Función global para recalcular paginación después de filtros
    window.recalcularPaginacion = function() {
        // Limpiar paginación existente
        paginationContainer.innerHTML = '';
        
        // Obtener filas visibles (no ocultas por filtros)
        const filasVisibles = Array.from(tbody.querySelectorAll("tr:not([style*='display: none'])"));
        
        if (filasVisibles.length > rowsPerPage) {
            // Crear nueva paginación solo para filas visibles
            showPageForFiltered(1, filasVisibles);
        } else {
            // Si hay pocas filas, mostrar todas
            filasVisibles.forEach(row => row.style.display = "");
        }
    };
    
    function showPageForFiltered(page, filasVisibles) {
      const totalPaginasFiltered = Math.ceil(filasVisibles.length / rowsPerPage);
      if (totalPaginasFiltered <= 0) return;

      const safePage = Math.max(1, Math.min(page, totalPaginasFiltered));
        const start = (safePage - 1) * rowsPerPage;
        const end = start + rowsPerPage;

        // Ocultar todas las filas primero
        rows.forEach(row => row.style.display = "none");
        
        // Mostrar solo las filas visibles de la página actual
        filasVisibles.forEach((row, i) => {
            row.style.display = i >= start && i < end ? "" : "none";
        });

        renderPagination(safePage, totalPaginasFiltered, (newPage) => showPageForFiltered(newPage, filasVisibles));
    }
  });