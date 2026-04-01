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
        rowsPerPage = 10; // 10 clientes por página
    } else {
        rowsPerPage = 8; // 8 rentas/cotizaciones por página
    }
    
    const tbody = table.querySelector("tbody");
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const totalPages = Math.ceil(rows.length / rowsPerPage);
    const paginationContainer = document.getElementById("pagination-container");

    function showPage(page) {
      const start = (page - 1) * rowsPerPage;
      const end = start + rowsPerPage;

      rows.forEach((row, i) => {
        row.style.display = i >= start && i < end ? "" : "none";
      });

      // Marcar el botón activo
      Array.from(paginationContainer.querySelectorAll("li.page-item")).forEach((btn, index) => {
        btn.classList.toggle("active", index === page);
      });
    }

    function createPaginationButtons() {
      const ul = document.createElement("ul");
      ul.className = "pagination";

      // Botón anterior
      const prevBtn = document.createElement("li");
      prevBtn.className = "page-item";
      prevBtn.innerHTML = `<a class="page-link" href="#">&laquo;</a>`;
      ul.appendChild(prevBtn);

      for (let i = 1; i <= totalPages; i++) {
        const li = document.createElement("li");
        li.className = "page-item";
        li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
        li.addEventListener("click", () => {
          showPage(i);
        });
        ul.appendChild(li);
      }

      // Botón siguiente
      const nextBtn = document.createElement("li");
      nextBtn.className = "page-item";
      nextBtn.innerHTML = `<a class="page-link" href="#">&raquo;</a>`;
      ul.appendChild(nextBtn);

      paginationContainer.appendChild(ul);

      // Evento para anterior y siguiente
      prevBtn.addEventListener("click", () => {
        const currentPage = ul.querySelector("li.active a")?.innerText || 1;
        if (currentPage > 1) showPage(parseInt(currentPage) - 1);
      });

      nextBtn.addEventListener("click", () => {
        const currentPage = ul.querySelector("li.active a")?.innerText || 1;
        if (currentPage < totalPages) showPage(parseInt(currentPage) + 1);
      });
    }

    if (rows.length > rowsPerPage) {
      createPaginationButtons();
      showPage(1);
    }
    
    // Función global para recalcular paginación después de filtros
    window.recalcularPaginacion = function() {
        // Limpiar paginación existente
        paginationContainer.innerHTML = '';
        
        // Obtener filas visibles (no ocultas por filtros)
        const filasVisibles = Array.from(tbody.querySelectorAll("tr:not([style*='display: none'])"));
        const totalPaginasActualizado = Math.ceil(filasVisibles.length / rowsPerPage);
        
        if (filasVisibles.length > rowsPerPage) {
            // Crear nueva paginación solo para filas visibles
            createPaginationButtonsForFiltered(filasVisibles);
            showPageForFiltered(1, filasVisibles);
        } else {
            // Si hay pocas filas, mostrar todas
            filasVisibles.forEach(row => row.style.display = "");
        }
    };
    
    function createPaginationButtonsForFiltered(filasVisibles) {
        const totalPaginasFiltered = Math.ceil(filasVisibles.length / rowsPerPage);
        const ul = document.createElement("ul");
        ul.className = "pagination";

        // Botón anterior
        const prevBtn = document.createElement("li");
        prevBtn.className = "page-item";
        prevBtn.innerHTML = `<a class="page-link" href="#">&laquo;</a>`;
        ul.appendChild(prevBtn);

        for (let i = 1; i <= totalPaginasFiltered; i++) {
            const li = document.createElement("li");
            li.className = "page-item";
            li.innerHTML = `<a class="page-link" href="#">${i}</a>`;
            li.addEventListener("click", () => {
                showPageForFiltered(i, filasVisibles);
            });
            ul.appendChild(li);
        }

        // Botón siguiente
        const nextBtn = document.createElement("li");
        nextBtn.className = "page-item";
        nextBtn.innerHTML = `<a class="page-link" href="#">&raquo;</a>`;
        ul.appendChild(nextBtn);

        paginationContainer.appendChild(ul);

        // Evento para anterior y siguiente
        prevBtn.addEventListener("click", () => {
            const currentPage = ul.querySelector("li.active a")?.innerText || 1;
            if (currentPage > 1) showPageForFiltered(parseInt(currentPage) - 1, filasVisibles);
        });

        nextBtn.addEventListener("click", () => {
            const currentPage = ul.querySelector("li.active a")?.innerText || 1;
            if (currentPage < totalPaginasFiltered) showPageForFiltered(parseInt(currentPage) + 1, filasVisibles);
        });
    }
    
    function showPageForFiltered(page, filasVisibles) {
        const start = (page - 1) * rowsPerPage;
        const end = start + rowsPerPage;

        // Ocultar todas las filas primero
        rows.forEach(row => row.style.display = "none");
        
        // Mostrar solo las filas visibles de la página actual
        filasVisibles.forEach((row, i) => {
            row.style.display = i >= start && i < end ? "" : "none";
        });

        // Marcar el botón activo
        Array.from(paginationContainer.querySelectorAll("li.page-item")).forEach((btn, index) => {
            btn.classList.toggle("active", index === page);
        });
    }
  });