const svg = (contenido) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${contenido}</svg>`;

export const libroAbierto = svg(
  '<path d="M12 7v14"/><path d="M3 5.5A2.5 2.5 0 0 1 5.5 3H12v16H5.5A2.5 2.5 0 0 0 3 21.5z"/><path d="M21 5.5A2.5 2.5 0 0 0 18.5 3H12v16h6.5a2.5 2.5 0 0 1 2.5 2.5z"/>',
);
export const microfono = svg(
  '<rect x="9" y="2.5" width="6" height="12" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v4M9 22h6"/>',
);
export const enviar = svg('<path d="m22 2-7 20-4-9-9-4z"/><path d="M22 2 11 13"/>');
export const detener = svg('<rect x="5" y="5" width="14" height="14" rx="2"/>');
export const play = svg('<path d="m8 5 12 7-12 7z"/>');
export const repetir = svg('<path d="m17 2 4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/>');
export const luna = svg('<path d="M20.5 15.5A8.5 8.5 0 0 1 8.5 3.5 8.7 8.7 0 1 0 20.5 15.5Z"/>');
export const sol = svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42"/>');
export const chat = svg('<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H6l-3 2v-6.5A7.5 7.5 0 1 1 20 11.5Z"/><path d="M8 11h8m-8 3h5"/>');
export const catalogo = svg('<path d="M3 21V5l6-2v18M9 5l6-2v18M15 5l6-2v18"/><path d="M5.5 7h1m5-1h1m5-1h1M5.5 11h1m5-1h1m5-1h1M5.5 15h1m5-1h1m5-1h1"/>');
export const comparar = svg('<path d="M12 3v18M3 6h6v12H3zm12 0h6v12h-6z"/><path d="M5 9h2m10 0h2"/>');
export const bitacora = svg('<path d="M4 5h10M4 10h8M4 15h6"/><path d="M17 14v4l3 2"/><circle cx="17" cy="17" r="5"/>');
export const usuario = svg('<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>');
export const cerrarSesion = svg('<path d="M10 17l5-5-5-5m5 5H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/>');
export const reservar = svg('<path d="M6 4.5A2.5 2.5 0 0 1 8.5 2h7A2.5 2.5 0 0 1 18 4.5V22l-6-4-6 4z"/>');
export const resumen = svg('<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/>');
export const fuente = svg('<path d="M6 3h8l4 4v14H6z"/><path d="M14 3v5h5M9 12h6m-6 4h6"/>');
export const alerta = svg('<path d="m12 3 9 16H3z"/><path d="M12 9v4m0 3h.01"/>');
export const check = svg('<path d="m5 12 4 4L19 6"/>');
export const x = svg('<path d="m6 6 12 12M18 6 6 18"/>');
export const buscar = svg('<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 5 5"/>');
export const filtro = svg('<path d="M3 5h18l-7 8v5l-4 3v-8z"/>');

export const iconos = {
  "libro-abierto": libroAbierto,
  microfono,
  enviar,
  detener,
  play,
  repetir,
  luna,
  sol,
  chat,
  catalogo,
  comparar,
  bitacora,
  usuario,
  "cerrar-sesion": cerrarSesion,
  reservar,
  resumen,
  fuente,
  alerta,
  check,
  x,
  buscar,
  filtro,
};
