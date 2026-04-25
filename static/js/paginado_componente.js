class PaginadorTabla {
  constructor(tabla, opciones = {}) {
    this.tabla = tabla;
    this.tbody = tabla.querySelector("tbody");
    this.filas = Array.from(this.tbody.querySelectorAll("tr"));

    this.filasPorPagina = opciones.filasPorPagina || 10;
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

    for (let i = 1; i <= this.totalPaginas; i++) {
      const li = this.crearItem(i, i, false, i === this.paginaActual);
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
    new PaginadorTabla(tabla, { filasPorPagina: 8 });
  });
}

document.addEventListener("DOMContentLoaded", iniciarPaginacion);

document.querySelectorAll('[data-bs-toggle="tab"]').forEach(tab => {
  tab.addEventListener('shown.bs.tab', () => {
    iniciarPaginacion();
  });
});