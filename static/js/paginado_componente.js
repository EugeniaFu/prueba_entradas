class PaginadorTabla {
  constructor(tabla, opciones = {}) {
    this.tabla = tabla;
    this.tbody = tabla.querySelector("tbody");
    this.filas = Array.from(this.tbody.querySelectorAll("tr"));

    this.filasPorPagina = opciones.filasPorPagina || 8;
    this.paginaActual = 1;

    // Busca el contenedor de paginación más cercano
    this.contenedor = tabla.parentElement.querySelector(".paginacion");

    if (!this.contenedor) {
      console.warn("No se encontró contenedor .paginacion para:", tabla);
      return;
    }

    this.totalPaginas = Math.ceil(this.filas.length / this.filasPorPagina);

    this.render();
  }

  mostrarPagina(pagina) {
    this.paginaActual = pagina;

    const inicio = (pagina - 1) * this.filasPorPagina;
    const fin = inicio + this.filasPorPagina;

    this.filas.forEach((fila, index) => {
      fila.style.display = (index >= inicio && index < fin) ? "" : "none";
    });

    this.renderBotones();
  }

  renderBotones() {
    this.contenedor.innerHTML = "";

    const ul = document.createElement("ul");
    ul.className = "pagination justify-content-center";

    // Botón anterior
    ul.appendChild(this.crearItem("«", this.paginaActual - 1, this.paginaActual === 1));

    // Lógica para mostrar páginas con elipsis
    const rango = 2; // Páginas antes y después de la actual
    const paginasVisibles = new Set();

    // Siempre mostrar primera y última página
    paginasVisibles.add(1);
    paginasVisibles.add(this.totalPaginas);

    // Añadir página actual y páginas adyacentes
    for (let i = Math.max(1, this.paginaActual - rango); i <= Math.min(this.totalPaginas, this.paginaActual + rango); i++) {
      paginasVisibles.add(i);
    }

    // Convertir a array y ordenar
    const paginasOrdenadas = Array.from(paginasVisibles).sort((a, b) => a - b);

    // Renderizar páginas con elipsis
    for (let i = 0; i < paginasOrdenadas.length; i++) {
      const pagina = paginasOrdenadas[i];
      const paginaAnterior = paginasOrdenadas[i - 1];

      // Añadir elipsis si hay un hueco
      if (paginaAnterior && pagina - paginaAnterior > 1) {
        const li = document.createElement("li");
        li.className = "page-item disabled";
        const span = document.createElement("span");
        span.className = "page-link";
        span.innerText = "...";
        li.appendChild(span);
        ul.appendChild(li);
      }

      // Añadir número de página
      const li = this.crearItem(pagina, pagina, false, pagina === this.paginaActual);
      ul.appendChild(li);
    }

    // Botón siguiente
    ul.appendChild(this.crearItem("»", this.paginaActual + 1, this.paginaActual === this.totalPaginas));

    this.contenedor.appendChild(ul);
  }

  crearItem(texto, pagina, deshabilitado = false, activo = false) {
    const li = document.createElement("li");
    li.className = `page-item ${deshabilitado ? "disabled" : ""} ${activo ? "active" : ""}`;

    const btn = document.createElement("button");
    btn.className = "page-link";
    btn.innerText = texto;

    if (!deshabilitado) {
      btn.addEventListener("click", () => this.mostrarPagina(pagina));
    }

    li.appendChild(btn);
    return li;
  }

  render() {
    this.mostrarPagina(1);
  }
}

function iniciarPaginacion() {
  document.querySelectorAll(".tabla-paginada").forEach(tabla => {
    // Allow per-table override via `data-filas` attribute, fallback to 8
    const filasAttr = parseInt(tabla.dataset.filas);
    const filas = Number.isInteger(filasAttr) && filasAttr > 0 ? filasAttr : 8;
    new PaginadorTabla(tabla, { filasPorPagina: filas });
  });
}

document.addEventListener("DOMContentLoaded", iniciarPaginacion);

document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
  tab.addEventListener('shown.bs.tab', () => {
    iniciarPaginacion();
  });
});