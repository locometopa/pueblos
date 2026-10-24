/* PUEBLOS · panel web de gestión.
   Guarda los cambios directamente en el repositorio de GitHub (carpeta datos/) y GitHub Actions
   rehace la web. Funciona en el móvil. El acceso es con un token personal que solo se guarda en
   este navegador. */
(function () {
  'use strict';

  // ------------------------------------------------------------------ utilidades
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
  const clonar = (o) => JSON.parse(JSON.stringify(o));
  const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const local = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin almacenamiento */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* nada */ } },
  };

  const API = window.PUEBLOS_API || 'https://api.github.com';
  const NOMINATIM = window.PUEBLOS_NOMINATIM || 'https://nominatim.openstreetmap.org';
  const WIKI = window.PUEBLOS_WIKI || 'https://es.wikipedia.org/w/api.php';
  const WIKIDATA = window.PUEBLOS_WIKIDATA || 'https://www.wikidata.org/w/api.php';
  const COMMONS = window.PUEBLOS_COMMONS || 'https://commons.wikimedia.org/w/api.php';
  const RAW = window.PUEBLOS_RAW || 'https://raw.githubusercontent.com';
  const SPARQL = window.PUEBLOS_SPARQL || 'https://query.wikidata.org/sparql';
  const MARGEN_HORAS = 2;
  const COMUNIDADES = ['Andalucía', 'Aragón', 'Asturias', 'Islas Baleares', 'Canarias', 'Cantabria',
    'Castilla-La Mancha', 'Castilla y León', 'Cataluña', 'Comunidad Valenciana', 'Extremadura', 'Galicia',
    'Comunidad de Madrid', 'Región de Murcia', 'Navarra', 'País Vasco', 'La Rioja', 'Ceuta', 'Melilla', 'Fuera de España'];
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];

  function normalizar(t) {
    return (t || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
  }
  const slugify = (t) => normalizar(t).replace(/ /g, '-') || 'pueblo';
  const dos = (n) => String(n).padStart(2, '0');
  function ahora() {
    const d = new Date();
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
  }
  const hoy = () => ahora().slice(0, 10);
  function fechaValida(t) {
    const m = /^(\d{4})(?:-(\d{2})(?:-(\d{2}))?)?$/.exec(t || '');
    if (!m) return false;
    if (m[2] && (+m[2] < 1 || +m[2] > 12)) return false;
    if (m[3]) { const d = new Date(+m[1], +m[2] - 1, +m[3]); if (d.getDate() !== +m[3]) return false; }
    return true;
  }
  function fechaBonita(iso) {
    const p = String(iso || '').split('-'), mes = MESES[+p[1] - 1];
    if (p.length === 3 && mes) return `${+p[2]} de ${mes} de ${p[0]}`;
    if (p.length === 2 && mes) return `${mes} de ${p[0]}`;
    return String(iso || '');
  }

  function fechaCorta(iso) {
    const p = String(iso || '').split('-'), mes = MESES[+p[1] - 1];
    if (p.length >= 2 && mes) return `${mes.slice(0, 3)} ${p[0]}`;
    return p[0] || '';
  }

  function puebloVacio(nombre) {
    return {
      slug: '', nombre: nombre || '', provincia: '', comunidad: '', pais: 'España', lat: null, lon: null,
      fechas_visita: [], wiki: {}, texto_ia: '', notas: '', fotos: [], portada: '', publicar: true,
      estado: 'visitado', creado: ahora(), modificado: '',
    };
  }

  function ordenarFotos(p) {
    p.fotos.sort((a, b) => {
      const ka = [a.credito ? 1 : 0, a.fecha || '9999', a.archivo];
      const kb = [b.credito ? 1 : 0, b.fecha || '9999', b.archivo];
      for (let i = 0; i < 3; i++) { if (ka[i] < kb[i]) return -1; if (ka[i] > kb[i]) return 1; }
      return 0;
    });
  }
  function rematar(p) {
    p.fechas_visita = Array.from(new Set((p.fechas_visita || []).filter(Boolean))).sort();
    ordenarFotos(p);
    const nombres = p.fotos.map((f) => f.archivo);
    if (!nombres.includes(p.portada)) p.portada = nombres[0] || '';
    p.modificado = ahora();
    return p;
  }

  // ------------------------------------------------------------------ avisos / espera
  let temporizadorAviso = null;
  function aviso(texto, error) {
    const el = $('#aviso');
    el.textContent = texto;
    el.classList.toggle('error', !!error);
    el.classList.add('ver');
    clearTimeout(temporizadorAviso);
    temporizadorAviso = setTimeout(() => el.classList.remove('ver'), error ? 6000 : 3500);
  }
  function espera(texto, fraccion) {
    $('#espera').hidden = false;
    $('#espera-texto').textContent = texto;
    $('#espera-barra').style.width = fraccion == null ? '0' : Math.round(fraccion * 100) + '%';
  }
  const finEspera = () => { $('#espera').hidden = true; };

  // ------------------------------------------------------------------ contraseña (token cifrado)
  /* El token se guarda cifrado (AES-256-GCM, clave derivada de la contraseña con PBKDF2-SHA256)
     en acceso_panel.json, que se publica junto al panel. Sin la contraseña no sirve de nada. */
  const ITERACIONES = 600000;
  const aB64 = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf)));
  const deB64 = (t) => Uint8Array.from(atob(t), (c) => c.charCodeAt(0));
  async function claveDe(clave, sal, iter) {
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(clave), 'PBKDF2', false, ['deriveKey']);
    return crypto.subtle.deriveKey({ name: 'PBKDF2', salt: sal, iterations: iter, hash: 'SHA-256' },
      base, { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']);
  }
  async function cifrarToken(token, repo, clave) {
    const sal = crypto.getRandomValues(new Uint8Array(16)), iv = crypto.getRandomValues(new Uint8Array(12));
    const k = await claveDe(clave, sal, ITERACIONES);
    const datos = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, k, new TextEncoder().encode(JSON.stringify({ token, repo })));
    return { version: 1, kdf: 'PBKDF2-SHA256', iteraciones: ITERACIONES, sal: aB64(sal), iv: aB64(iv), datos: aB64(datos), creado: ahora() };
  }
  async function descifrarToken(acceso, clave) {
    const k = await claveDe(clave, deB64(acceso.sal), acceso.iteraciones || ITERACIONES);
    try {
      const plano = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: deB64(acceso.iv) }, k, deB64(acceso.datos));
      return JSON.parse(new TextDecoder().decode(plano));
    } catch (e) { throw new Error('Contraseña incorrecta.'); }
  }

  // ------------------------------------------------------------------ GitHub
  class ErrorConflicto extends Error {}
  class GitHub {
    constructor(token, repo, rama) { this.token = token; this.repo = repo; this.rama = rama || 'main'; }
    async pedir(metodo, ruta, cuerpo) {
      const r = await fetch(API + ruta, {
        method: metodo,
        headers: {
          Authorization: 'Bearer ' + this.token, Accept: 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}),
        },
        body: cuerpo ? JSON.stringify(cuerpo) : undefined,
      });
      if (r.status === 404) return null;
      if (r.status === 401) throw new Error('El token no es válido o ha caducado. Ve a Ajustes y pon uno nuevo.');
      if (r.status === 403) {
        const t = await r.text();
        throw new Error(t.includes('rate limit') ? 'GitHub pide esperar un poco (límite de uso). Prueba en unos minutos.'
          : 'El token no tiene permiso para escribir en el repositorio (Contents: Read and write).');
      }
      if (r.status === 409 || r.status === 422) {
        const t = await r.text();
        if (/fast.forward|Update is not a fast forward|reference/i.test(t)) throw new ErrorConflicto(t);
        throw new Error('GitHub: ' + t.slice(0, 200));
      }
      if (!r.ok) throw new Error(`GitHub respondió ${r.status}`);
      return r.status === 204 ? {} : r.json();
    }
    ruta(p) { return p.split('/').map(encodeURIComponent).join('/'); }
    async comprobar() {
      const r = await this.pedir('GET', `/repos/${this.repo}`);
      if (!r) throw new Error(`No encuentro el repositorio ${this.repo}, o el token no tiene acceso a él.`);
      if (r.permissions && r.permissions.push === false) throw new Error('El token no tiene permiso de escritura en el repositorio.');
      return r;
    }
    async cabeza() {
      const ref = await this.pedir('GET', `/repos/${this.repo}/git/ref/heads/${this.rama}`);
      if (!ref) throw new Error(`El repositorio no tiene la rama «${this.rama}». Publica primero desde el programa de Windows.`);
      const commit = await this.pedir('GET', `/repos/${this.repo}/git/commits/${ref.object.sha}`);
      return { commit: ref.object.sha, arbol: commit.tree.sha };
    }
    async arbol(sha) {
      const r = await this.pedir('GET', `/repos/${this.repo}/git/trees/${sha}?recursive=1`);
      return (r && r.tree) || [];
    }
    async blobTexto(sha) {
      const r = await this.pedir('GET', `/repos/${this.repo}/git/blobs/${sha}`);
      return decodificar(r.content);
    }
    async leerJson(ruta, ref) {
      const r = await this.pedir('GET', `/repos/${this.repo}/contents/${this.ruta(ruta)}?ref=${ref}`);
      if (!r || Array.isArray(r)) return null;
      try { return JSON.parse(decodificar(r.content)); } catch (e) { return null; }
    }
    async crearBlob(base64) {
      const r = await this.pedir('POST', `/repos/${this.repo}/git/blobs`, { content: base64, encoding: 'base64' });
      return r.sha;
    }
    async crearArbol(base, entradas) {
      const r = await this.pedir('POST', `/repos/${this.repo}/git/trees`, { base_tree: base, tree: entradas });
      return r.sha;
    }
    async crearCommit(mensaje, arbol, padre) {
      const r = await this.pedir('POST', `/repos/${this.repo}/git/commits`, { message: mensaje, tree: arbol, parents: [padre] });
      return r.sha;
    }
    async moverRama(sha) {
      await this.pedir('PATCH', `/repos/${this.repo}/git/refs/heads/${this.rama}`, { sha, force: false });
    }
  }
  function decodificar(b64) {
    const bin = atob((b64 || '').replace(/\s/g, ''));
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new TextDecoder('utf-8').decode(bytes);
  }
  async function enParalelo(lista, n, fn) {
    const res = new Array(lista.length);
    let i = 0;
    await Promise.all(Array.from({ length: Math.min(n, lista.length) }, async () => {
      while (i < lista.length) { const k = i++; res[k] = await fn(lista[k], k); }
    }));
    return res;
  }

  // ------------------------------------------------------------------ estado
  const E = {
    gh: null, repo: '', rama: 'main', cabeza: null, pueblos: {}, archivos: {}, locales: {},
    vista: 'visitados', filtro: '', editor: null, shaFotos: null, acceso: null,
  };

  async function cargarTodo() {
    espera('Cargando tus pueblos…');
    try {
      const { commit, arbol } = await E.gh.cabeza();
      const lista = await E.gh.arbol(arbol);
      E.cabeza = commit;
      E.shaFotos = commit;   // las fotos ya existentes se piden siempre a esta versión (así se aprovecha la caché)
      E.archivos = {};
      const jsons = [];
      for (const it of lista) {
        const m = /^datos\/([^/]+)\/(.+)$/.exec(it.path);
        if (!m || m[1].startsWith('_') || it.type !== 'blob') continue;
        (E.archivos[m[1]] = E.archivos[m[1]] || []).push(it.path);
        if (m[2] === 'pueblo.json') jsons.push({ slug: m[1], sha: it.sha });
      }
      const pueblos = {};
      let hechos = 0;
      await enParalelo(jsons, 6, async (j) => {
        try {
          const p = Object.assign(puebloVacio(), JSON.parse(await E.gh.blobTexto(j.sha)));
          p.slug = p.slug || j.slug;
          pueblos[j.slug] = p;
        } catch (e) { console.warn('No se pudo leer', j.slug, e); }
        espera('Cargando tus pueblos…', ++hechos / jsons.length);
      });
      E.pueblos = pueblos;
    } finally { finEspera(); }
  }

  /* Guarda en un solo commit. ops: [{slug, aplicar(fresco|null) -> pueblo|null}];
     binarios: [{ruta, blob}]; borrar: [ruta]. Si alguien (el programa) subió algo a la vez,
     se vuelve a leer lo último y se repite: así no se pisan los cambios. */
  async function guardar(ops, binarios, borrar, mensaje, textos) {
    binarios = binarios || []; borrar = borrar || []; textos = textos || [];
    const shas = {};
    for (let i = 0; i < binarios.length; i++) {
      espera(`Subiendo fotos (${i + 1} de ${binarios.length})…`, i / binarios.length);
      shas[binarios[i].ruta] = await E.gh.crearBlob(await aBase64(binarios[i].blob));
    }
    espera('Guardando en GitHub…', 1);
    try {
      for (let intento = 0; intento < 4; intento++) {
        const { commit, arbol } = await E.gh.cabeza();
        const entradas = [];
        const resultado = {};
        for (const op of ops) {
          const fresco = await E.gh.leerJson(`datos/${op.slug}/pueblo.json`, commit);
          const p = op.aplicar(fresco ? Object.assign(puebloVacio(), fresco) : null);
          if (!p) continue;
          p.slug = op.slug;
          rematar(p);
          entradas.push({ path: `datos/${op.slug}/pueblo.json`, mode: '100644', type: 'blob', content: JSON.stringify(p, null, 2) });
          resultado[op.slug] = p;
        }
        for (const ruta in shas) entradas.push({ path: ruta, mode: '100644', type: 'blob', sha: shas[ruta] });
        for (const ruta of borrar) entradas.push({ path: ruta, mode: '100644', type: 'blob', sha: null });
        for (const t of textos) entradas.push({ path: t.ruta, mode: '100644', type: 'blob', content: t.contenido });
        if (!entradas.length) return {};
        const nuevoArbol = await E.gh.crearArbol(arbol, entradas);
        const nuevo = await E.gh.crearCommit(mensaje, nuevoArbol, commit);
        try {
          await E.gh.moverRama(nuevo);
        } catch (e) {
          if (e instanceof ErrorConflicto && intento < 3) { await dormir(600); continue; }
          throw e;
        }
        E.cabeza = nuevo;
        Object.assign(E.pueblos, resultado);
        for (const ruta in shas) {
          const slug = ruta.split('/')[1];
          (E.archivos[slug] = E.archivos[slug] || []).push(ruta);
        }
        for (const ruta of borrar) {
          const slug = ruta.split('/')[1];
          E.archivos[slug] = (E.archivos[slug] || []).filter((x) => x !== ruta);
        }
        return resultado;
      }
      throw new Error('No se pudo guardar: había cambios a la vez. Vuelve a intentarlo.');
    } finally { finEspera(); }
  }

  function urlFoto(slug, archivo, grande) {
    const ruta = `datos/${slug}/${grande ? 'fotos' : 'mini'}/${archivo}`;
    if (E.locales[ruta]) return E.locales[ruta];
    return `${RAW}/${E.repo}/${E.shaFotos || E.rama}/${ruta.split('/').map(encodeURIComponent).join('/')}`;
  }

  function buscarPueblo(nombre, provincia) {
    const nn = normalizar(nombre), np = normalizar(provincia);
    return Object.values(E.pueblos).find((p) => normalizar(p.nombre) === nn &&
      (!np || !p.provincia || normalizar(p.provincia) === np)) || null;
  }
  function slugLibre(nombre, provincia, reservados) {
    const ocupado = (s) => E.pueblos[s] || (E.archivos[s] && E.archivos[s].length) || (reservados && reservados.has(s));
    let base = slugify(nombre);
    if (!ocupado(base)) return base;
    if (provincia) {
      const cp = `${base}-${slugify(provincia)}`;
      if (!ocupado(cp)) return cp;
      base = cp;
    }
    let n = 2;
    while (ocupado(`${base}-${n}`)) n++;
    return `${base}-${n}`;
  }
  let contadorFotos = 0;
  const nombreFoto = () => `w${Date.now().toString(36)}${(contadorFotos++).toString(36).padStart(3, '0')}.jpg`;

  // ------------------------------------------------------------------ imágenes
  function cargarImagen(blob) {
    return new Promise((ok, mal) => {
      const url = URL.createObjectURL(blob);
      const img = new Image();
      img.onload = () => ok({ img, url });
      img.onerror = () => { URL.revokeObjectURL(url); mal(new Error('No puedo abrir esta imagen (¿formato HEIC?)')); };
      img.src = url;
    });
  }
  function reducir(img, lado, calidad) {
    const esc = Math.min(1, lado / Math.max(img.naturalWidth, img.naturalHeight));
    const c = document.createElement('canvas');
    c.width = Math.max(1, Math.round(img.naturalWidth * esc));
    c.height = Math.max(1, Math.round(img.naturalHeight * esc));
    const ctx = c.getContext('2d');
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(img, 0, 0, c.width, c.height);
    return new Promise((r) => c.toBlob(r, 'image/jpeg', calidad));
  }
  /* Copia reducida y sin metadatos (el lienzo no conserva el GPS) */
  async function prepararFoto(blob) {
    const { img, url } = await cargarImagen(blob);
    try {
      return { grande: await reducir(img, 1600, 0.85), mini: await reducir(img, 600, 0.8) };
    } finally { URL.revokeObjectURL(url); }
  }
  const aBase64 = (blob) => new Promise((ok, mal) => {
    const fr = new FileReader();
    fr.onload = () => ok(String(fr.result).split(',')[1]);
    fr.onerror = () => mal(fr.error);
    fr.readAsDataURL(blob);
  });
  async function leerMeta(archivo) {
    const m = { archivo, lat: null, lon: null, momento: null, fecha: '' };
    try {
      const d = await window.exifr.parse(archivo, { gps: true, tiff: true, exif: true });
      if (d) {
        if (typeof d.latitude === 'number' && typeof d.longitude === 'number' &&
          (Math.abs(d.latitude) > 0.0001 || Math.abs(d.longitude) > 0.0001)) {
          m.lat = +d.latitude.toFixed(6); m.lon = +d.longitude.toFixed(6);
        }
        const f = d.DateTimeOriginal || d.CreateDate || d.ModifyDate;
        if (f instanceof Date && !isNaN(f)) {
          m.momento = f.getTime();
          m.fecha = `${f.getFullYear()}-${dos(f.getMonth() + 1)}-${dos(f.getDate())}`;
        }
      }
    } catch (e) { /* sin EXIF */ }
    return m;
  }
  const claveOriginal = (archivo) => `${archivo.name}|${archivo.size}`;

  // ------------------------------------------------------------------ mapa (OpenStreetMap)
  let ultimoMapa = 0;
  const cacheGeo = (() => { try { return JSON.parse(local.get('pueblos-geo') || '{}'); } catch (e) { return {}; } })();
  async function nominatim(ruta, params) {
    const pausa = 1100 - (Date.now() - ultimoMapa);
    if (pausa > 0) await dormir(pausa);
    ultimoMapa = Date.now();
    const q = new URLSearchParams(Object.assign({ format: 'jsonv2', addressdetails: 1, 'accept-language': 'es' }, params));
    const r = await fetch(`${NOMINATIM}${ruta}?${q}`);
    if (!r.ok) throw new Error('El mapa no responde (' + r.status + ')');
    return r.json();
  }
  function desdeDireccion(a, lat, lon) {
    a = a || {};
    const nombre = a.village || a.town || a.city || a.municipality || a.hamlet || a.suburb || '';
    const comunidad = a.state || '';
    return { nombre, provincia: a.province || a.state_district || a.county || comunidad, comunidad, pais: a.country || '', lat, lon };
  }
  async function geoInverso(lat, lon) {
    const k = `${lat.toFixed(3)},${lon.toFixed(3)}`;
    if (cacheGeo[k]) return cacheGeo[k];
    const js = await nominatim('/reverse', { lat, lon, zoom: 14 });
    if (!js || !js.address) return null;
    const res = desdeDireccion(js.address, lat, lon);
    cacheGeo[k] = res;
    local.set('pueblos-geo', JSON.stringify(cacheGeo));
    return res;
  }
  async function geoBuscar(texto) {
    const js = await nominatim('/search', { q: texto, limit: 8 });
    return (js || []).map((x) => Object.assign(desdeDireccion(x.address, +x.lat, +x.lon),
      { descripcion: x.display_name || '' }, x.address ? {} : { nombre: x.name || texto }))
      .map((r) => (r.nombre ? r : Object.assign(r, { nombre: texto })));
  }

  // ------------------------------------------------------------------ Wikipedia / Wikidata
  async function wget(url, params) {
    const q = new URLSearchParams(Object.assign({ format: 'json', origin: '*' }, params));
    const r = await fetch(`${url}?${q}`);
    if (!r.ok) throw new Error('Wikipedia no responde (' + r.status + ')');
    return r.json();
  }
  const baseTitulo = (t) => normalizar(t.split(' (')[0].split(',')[0]);
  async function wikiTitulo(nombre, provincia, lat, lon) {
    const objetivo = normalizar(nombre);
    let cerca = [];
    if (lat != null && lon != null) {
      const js = await wget(WIKI, { action: 'query', list: 'geosearch', gscoord: `${lat}|${lon}`, gsradius: 10000, gslimit: 50 });
      cerca = ((js.query || {}).geosearch || []).map((g) => g.title);
      const t = cerca.find((x) => baseTitulo(x) === objetivo);
      if (t) return t;
    }
    const js = await wget(WIKI, { action: 'query', list: 'search', srsearch: `${nombre} ${provincia || ''}`.trim(), srlimit: 10 });
    const texto = ((js.query || {}).search || []).map((s) => s.title);
    return texto.find((x) => baseTitulo(x) === objetivo) ||
      cerca.concat(texto).find((x) => objetivo && normalizar(x).includes(objetivo)) || null;
  }
  async function wikiDatos(titulo) {
    const js = await wget(WIKI, { action: 'query', prop: 'extracts|pageprops|info', titles: titulo, exintro: 1, explaintext: 1, redirects: 1, inprop: 'url' });
    const pag = Object.values((js.query || {}).pages || {})[0] || {};
    if ('missing' in pag) return null;
    const props = pag.pageprops || {};
    const res = { titulo: pag.title || titulo, url: pag.fullurl || '', extracto: (pag.extract || '').trim(), desambiguacion: 'disambiguation' in props };
    if (props.wikibase_item) {
      res.wikidata = props.wikibase_item;
      try { Object.assign(res, await wikidata(props.wikibase_item)); } catch (e) { /* sin datos extra */ }
    }
    return res;
  }
  async function wikidata(qid) {
    const js = await wget(WIKIDATA, { action: 'wbgetentities', ids: qid, props: 'claims' });
    const claims = (((js.entities || {})[qid]) || {}).claims || {};
    const mejor = (prop) => {
      const lista = (claims[prop] || []).filter((c) => c.rank !== 'deprecated' && c.mainsnak && c.mainsnak.datavalue);
      if (!lista.length) return null;
      const pref = lista.find((c) => c.rank === 'preferred');
      if (pref) return pref;
      const fecha = (c) => { try { return c.qualifiers.P585[0].datavalue.value.time; } catch (e) { return ''; } };
      return lista.reduce((a, b) => (fecha(b) > fecha(a) ? b : a));
    };
    const valor = (prop) => { const c = mejor(prop); return c ? c.mainsnak.datavalue.value : null; };
    const res = {};
    const pob = mejor('P1082');
    if (pob) {
      res.poblacion = Math.round(parseFloat(pob.mainsnak.datavalue.value.amount));
      try { res.poblacion_anio = pob.qualifiers.P585[0].datavalue.value.time.slice(1, 5); } catch (e) { /* sin año */ }
    }
    const alt = valor('P2044'); if (alt) res.altitud = Math.round(parseFloat(alt.amount));
    const sup = valor('P2046'); if (sup) res.superficie = Math.round(parseFloat(sup.amount) * 100) / 100;
    const escudo = valor('P94'); if (escudo) res.escudo = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + escudo.replace(/ /g, '_') + '?width=160';
    const web = valor('P856'); if (web) res.web = web;
    const coord = valor('P625'); if (coord) { res.lat = coord.latitude; res.lon = coord.longitude; }
    return res;
  }
  async function wikiTodo(nombre, provincia, lat, lon) {
    const titulo = await wikiTitulo(nombre, provincia, lat, lon);
    if (!titulo) return null;
    let d = await wikiDatos(titulo);
    if (d && d.desambiguacion && provincia) {
      const otro = await wikiTitulo(`${nombre} (${provincia})`, provincia);
      if (otro && otro !== titulo) d = await wikiDatos(otro);
    }
    return d ? wikiAmpliar(d) : d;
  }
  // --- información ampliada: apartados del artículo, qué ver, gentilicio y patrón
  const APARTADOS = [
    ['historia', ['historia']],
    ['patrimonio', ['patrimonio', 'monumento', 'lugares de interes', 'arquitectura', 'que ver', 'edificios']],
    ['fiestas', ['fiesta', 'festividad', 'celebracion']],
    ['gastronomia', ['gastronomia', 'cocina', 'productos tipicos']],
    ['cultura', ['cultura', 'tradicion', 'folclore', 'costumbres']],
    ['leyendas', ['leyenda', 'curiosidad', 'mitologia', 'anecdota']],
    ['naturaleza', ['naturaleza', 'espacios naturales', 'medio ambiente', 'rutas', 'senderismo', 'turismo']],
    ['personajes', ['personajes', 'personalidades', 'hijos ilustres', 'vecinos ilustres']],
  ];
  const tipoApartado = (t) => { t = normalizar(t); const a = APARTADOS.find(([, ps]) => ps.some((p) => t.includes(p))); return a ? a[0] : null; };
  function recortar(t, max) {
    t = t.replace(/\n{3,}/g, '\n\n').trim();
    if (t.length <= max) return t;
    let c = t.lastIndexOf('\n\n', max);
    if (c < max * 0.5) c = t.lastIndexOf('. ', max) + 1;
    return t.slice(0, c).trimEnd() + ' …';
  }
  function partirSecciones(texto) {
    const res = {};
    let actual = null;
    for (const linea of (texto || '').split('\n')) {
      const m = /^(={2,6})\s*(.*?)\s*\1\s*$/.exec(linea.trim());
      if (m) {
        if (m[1].length === 2) {
          actual = tipoApartado(m[2]);
          if (actual && !res[actual]) res[actual] = { clave: actual, titulo: m[2], texto: [] };
          else if (actual) res[actual].texto.push('');
        } else if (actual) res[actual].texto.push('\n▸ ' + m[2]);
        continue;
      }
      if (actual) res[actual].texto.push(linea);
    }
    const out = [];
    for (const [clave] of APARTADOS) {
      if (!res[clave]) continue;
      const t = recortar(res[clave].texto.join('\n').replace(/\n▸/g, '\n\n▸'), 1600);
      if (t.length > 60) out.push({ clave, titulo: res[clave].titulo, texto: t });
    }
    return out;
  }
  async function wikiAmpliar(d) {
    try {
      const js = await wget(WIKI, { action: 'query', prop: 'extracts', titles: d.titulo, explaintext: 1, exsectionformat: 'wiki', redirects: 1 });
      const pag = Object.values((js.query || {}).pages || {})[0] || {};
      const s = partirSecciones(pag.extract || '');
      if (s.length) d.secciones = s;
    } catch (e) { console.warn(e); }
    const qid = d.wikidata;
    if (!qid) return d;
    try {
      const js = await wget(WIKIDATA, { action: 'wbgetentities', ids: qid, props: 'claims' });
      const claims = (((js.entities || {})[qid]) || {}).claims || {};
      const gent = (claims.P1549 || []).map((c) => c.mainsnak && c.mainsnak.datavalue && c.mainsnak.datavalue.value)
        .filter((v) => v && v.language === 'es').map((v) => v.text);
      if (gent.length) d.gentilicio = Array.from(new Set(gent.slice(0, 2))).join(', ');
      const pats = (claims.P417 || []).map((c) => c.mainsnak && c.mainsnak.datavalue && c.mainsnak.datavalue.value.id).filter(Boolean).slice(0, 3);
      if (pats.length) {
        const et = await wget(WIKIDATA, { action: 'wbgetentities', ids: pats.join('|'), props: 'labels', languages: 'es' });
        const n = Object.values(et.entities || {}).map((e) => ((e.labels || {}).es || {}).value).filter(Boolean);
        if (n.length) d.patron = n.join(', ');
      }
    } catch (e) { console.warn(e); }
    try {
      const q = `SELECT ?item ?itemLabel ?img ?art WHERE { ?item wdt:P131 wd:${qid} .
        { ?item wdt:P1435 ?p } UNION { ?item wdt:P31/wdt:P279* wd:Q570116 } UNION { ?item wdt:P31/wdt:P279* wd:Q16970 }
        UNION { ?item wdt:P31/wdt:P279* wd:Q23413 } UNION { ?item wdt:P31/wdt:P279* wd:Q33506 } UNION { ?item wdt:P31/wdt:P279* wd:Q12280 }
        OPTIONAL { ?item wdt:P18 ?img } OPTIONAL { ?art schema:about ?item ; schema:isPartOf <https://es.wikipedia.org/> }
        SERVICE wikibase:label { bd:serviceParam wikibase:language "es,en". } } LIMIT 80`;
      const r = await fetch(`${SPARQL}?${new URLSearchParams({ query: q, format: 'json' })}`, { headers: { Accept: 'application/sparql-results+json' } });
      if (!r.ok) throw new Error('Wikidata ' + r.status);
      const vistos = new Set();
      let lugares = [];
      for (const b of (await r.json()).results.bindings) {
        const item = b.item.value.split('/').pop(), nombre = (b.itemLabel || {}).value || '';
        if (vistos.has(item) || !nombre || /^Q\d+$/.test(nombre)) continue;
        vistos.add(item);
        const l = { nombre, url: (b.art || {}).value || `https://www.wikidata.org/wiki/${item}` };
        if (b.img) l._archivo = decodeURIComponent(b.img.value.split('/').pop()).replace(/_/g, ' ');
        lugares.push(l);
      }
      lugares.sort((a, b) => (('_archivo' in a) === ('_archivo' in b) ? (a.url.includes('wikipedia') === b.url.includes('wikipedia') ? 0 : a.url.includes('wikipedia') ? -1 : 1) : ('_archivo' in a ? -1 : 1)));
      lugares = lugares.slice(0, 12);
      const archivos = lugares.filter((l) => l._archivo).map((l) => 'File:' + l._archivo);
      if (archivos.length) {
        const js = await wget(COMMONS, { action: 'query', prop: 'imageinfo', iiprop: 'url|extmetadata', iiurlwidth: 500,
          titles: archivos.join('|'), iiextmetadatafilter: 'Artist|LicenseShortName|LicenseUrl' });
        const normal = {}; for (const n of (js.query || {}).normalized || []) normal[n.from] = n.to;
        const info = {}; for (const pg of Object.values((js.query || {}).pages || {})) { const ii = (pg.imageinfo || [{}])[0]; if (ii.thumburl) info[pg.title] = ii; }
        for (const l of lugares) {
          if (!l._archivo) continue;
          const t = normal['File:' + l._archivo] || 'File:' + l._archivo, ii = info[t];
          if (ii) {
            const meta = ii.extmetadata || {}, v = (k) => limpiar((meta[k] || {}).value);
            l.imagen = ii.thumburl;
            l.credito = { autor: v('Artist').slice(0, 120) || 'Autor desconocido', licencia: v('LicenseShortName') || 'Licencia libre',
              url_licencia: (meta.LicenseUrl || {}).value || '', fuente: ii.descriptionurl || '' };
          }
        }
      }
      for (const l of lugares) delete l._archivo;
      if (lugares.length) d.que_ver = lugares;
    } catch (e) { console.warn(e); }
    return d;
  }

  function aplicarWiki(p, d) {
    if (!d) return false;
    d = Object.assign({}, d);
    const lat = d.lat, lon = d.lon;
    delete d.lat; delete d.lon;
    if (p.lat == null && lat != null) { p.lat = +lat.toFixed(6); p.lon = +lon.toFixed(6); }
    p.wiki = d;
    return true;
  }

  // ------------------------------------------------------------------ Wikimedia Commons
  const DESCARTAR = /(mapa|map|location|localizaci|escudo|coat of arms|bandera|flag|logo|plano|\.svg|diagram|esquema|firma|signature)/i;
  const limpiar = (t) => { const d = document.createElement('div'); d.innerHTML = t || ''; return (d.textContent || '').replace(/\s+/g, ' ').trim(); };
  async function commonsConsulta(params, ancho) {
    const js = await wget(COMMONS, Object.assign({
      action: 'query', prop: 'imageinfo', iiprop: 'url|extmetadata|mime|size', iiurlwidth: ancho || 320,
      iiextmetadatafilter: 'Artist|LicenseShortName|LicenseUrl|ImageDescription|ObjectName',
    }, params));
    const pags = Object.values((js.query || {}).pages || {}).sort((a, b) => (a.index || 0) - (b.index || 0));
    const res = [];
    for (const pg of pags) {
      const info = (pg.imageinfo || [{}])[0];
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(info.mime) || !info.thumburl) continue;
      if (!ancho && (info.width || 0) < 800) continue;
      if (DESCARTAR.test(pg.title || '')) continue;
      const meta = info.extmetadata || {};
      const v = (k) => limpiar((meta[k] || {}).value);
      res.push({
        titulo: pg.title, miniatura: info.thumburl, pagina: info.descriptionurl || '',
        autor: v('Artist').slice(0, 120) || 'Autor desconocido', licencia: v('LicenseShortName') || 'Licencia libre',
        url_licencia: (meta.LicenseUrl || {}).value || '',
      });
    }
    return res;
  }
  async function commonsBuscar(p) {
    const vistos = new Set(), res = [];
    const consultas = [];
    if (p.lat != null) consultas.push({ generator: 'geosearch', ggscoord: `${p.lat}|${p.lon}`, ggsradius: 2000, ggsnamespace: 6, ggslimit: 40 });
    consultas.push({ generator: 'search', gsrsearch: `"${p.nombre}" ${p.provincia || ''} filetype:bitmap`.trim(), gsrnamespace: 6, gsrlimit: 40 });
    for (const c of consultas) {
      try {
        for (const it of await commonsConsulta(c)) if (!vistos.has(it.titulo)) { vistos.add(it.titulo); res.push(it); }
      } catch (e) { console.warn(e); }
    }
    return res;
  }

  // ------------------------------------------------------------------ instalar en el móvil
  const INST = {
    ev: null,
    ios: /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1),
    instalada: () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true,
    posible() { return !this.instalada() && (this.ev || this.ios); },
  };
  window.addEventListener('beforeinstallprompt', (ev) => {
    ev.preventDefault(); INST.ev = ev;
    if (!E.editor && $('.cab') && !$('#instalar-aviso')) pintarAvisoInstalar();
  });
  window.addEventListener('appinstalled', () => { INST.ev = null; const a = $('#instalar-aviso'); if (a) a.remove(); });
  const AYUDA_IOS = 'En Safari pulsa <b>Compartir</b> (el cuadrado con la flecha ↑) y luego <b>«Añadir a pantalla de inicio»</b>.';

  async function instalar(botonAyuda) {
    if (INST.ev) {
      INST.ev.prompt();
      const r = await INST.ev.userChoice; INST.ev = null;
      if (r && r.outcome === 'accepted') aviso('Panel instalado: búscalo en tu pantalla de inicio como «Gestión».');
      const a = $('#instalar-aviso'); if (a) a.remove();
    } else if (botonAyuda) {
      botonAyuda.hidden = !botonAyuda.hidden;
    }
  }

  function pintarAvisoInstalar() {
    if (!INST.posible() || local.get('pueblos-no-instalar')) return;
    const cab = $('.cab'); if (!cab || $('#instalar-aviso')) return;
    const div = document.createElement('div');
    div.id = 'instalar-aviso'; div.className = 'instalar-aviso';
    div.innerHTML = `<div class="fila-inst"><span>📲 Instala el panel en tu móvil y ábrelo como una app.</span>
      <button class="btn" id="inst-si">Instalar</button><button class="icono" id="inst-no" aria-label="No mostrar más">✕</button></div>
      <p class="ayuda" id="inst-ios" hidden>${AYUDA_IOS}</p>`;
    cab.after(div);
    $('#inst-si').onclick = () => instalar($('#inst-ios'));
    $('#inst-no').onclick = () => { local.set('pueblos-no-instalar', '1'); div.remove(); };
  }

  // ------------------------------------------------------------------ pantallas
  const app = () => $('#app');

  function cabecera(titulo, sub, izquierda, derecha) {
    return `<header class="cab">${izquierda || ''}<h1>${esc(titulo)}${sub ? `<small>${esc(sub)}</small>` : ''}</h1>${derecha || ''}</header>`;
  }

  function pantallaAcceso(error) {
    const repo = E.repo || '';
    app().innerHTML = `
      <div class="acceso">
        <h1>Gestión de mis pueblos</h1>
        <p>Para poder guardar cambios en tu web, el panel necesita un <b>token</b> de GitHub. Solo se crea una vez y se guarda únicamente en este navegador.</p>
        <ol>
          <li>Abre <a href="https://github.com/settings/personal-access-tokens/new" target="_blank" rel="noopener">github.com/settings/personal-access-tokens/new</a> (inicia sesión si te lo pide).</li>
          <li><b>Token name</b>: <code>Panel pueblos</code>. <b>Expiration</b>: el plazo que prefieras (por ejemplo, 1 año).</li>
          <li><b>Repository access</b> → <i>Only select repositories</i> → elige <code>${esc(repo.split('/')[1] || 'pueblos')}</code>.</li>
          <li><b>Permissions</b> → <i>Repository permissions</i> → <b>Contents</b> → <i>Read and write</i>.</li>
          <li>Pulsa <b>Generate token</b>, cópialo y pégalo aquí:</li>
        </ol>
        <div class="tarjeta">
          <label class="campo"><span>Token</span><input id="token" type="password" autocomplete="off" placeholder="github_pat_…"></label>
          <label class="campo"><span>Repositorio</span><input id="repo" value="${esc(repo)}" placeholder="usuario/pueblos"></label>
          ${error ? `<p class="ayuda" style="color:var(--peligro)">${esc(error)}</p>` : ''}
          <button class="btn ancho" id="entrar">Entrar</button>
        </div>
        <p class="ayuda">Nadie más puede cambiar tu web: sin el token, el panel no puede guardar nada.</p>
      </div>`;
    $('#entrar').onclick = async () => {
      const token = $('#token').value.trim(), r = $('#repo').value.trim();
      if (!token || !r.includes('/')) { pantallaAcceso('Falta el token o el repositorio.'); return; }
      E.gh = new GitHub(token, r, E.rama);
      espera('Comprobando el acceso…');
      try {
        await E.gh.comprobar();
        local.set('pueblos-token', token); local.set('pueblos-repo', r);
        E.repo = r;
        finEspera();
        await iniciar();
        if (!E.acceso || !local.get('pueblos-sin-clave')) setTimeout(() => dialogoContrasena(!E.acceso), 400);
      } catch (e) { finEspera(); pantallaAcceso(e.message); }
    };
  }

  function pantallaContrasena(acceso, error) {
    app().innerHTML = `
      <div class="acceso">
        <h1>Gestión de mis pueblos</h1>
        <p>Escribe tu contraseña del panel.</p>
        <div class="tarjeta">
          <label class="campo"><span>Contraseña</span><input id="clave" type="password" autocomplete="current-password"></label>
          ${error ? `<p class="ayuda" style="color:var(--peligro)">${esc(error)}</p>` : ''}
          <button class="btn ancho" id="entrar">Entrar</button>
        </div>
        <p class="ayuda"><a href="#" id="con-token">Entrar con el token</a> (por ejemplo, si has creado uno nuevo).</p>
      </div>`;
    const entrar = async () => {
      const clave = $('#clave').value;
      if (!clave) return;
      espera('Comprobando la contraseña…');
      try {
        const { token, repo } = await descifrarToken(acceso, clave);
        E.repo = repo || E.repo;
        E.gh = new GitHub(token, E.repo, E.rama);
        await E.gh.comprobar();
        local.set('pueblos-token', token); local.set('pueblos-repo', E.repo);
        finEspera();
        await iniciar();
      } catch (e) {
        finEspera();
        pantallaContrasena(acceso, /token/i.test(e.message)
          ? 'La contraseña es correcta, pero el token ha caducado o se ha borrado. Entra con un token nuevo y vuelve a poner la contraseña.'
          : e.message);
      }
    };
    $('#entrar').onclick = entrar;
    $('#clave').onkeydown = (ev) => { if (ev.key === 'Enter') entrar(); };
    setTimeout(() => $('#clave').focus(), 50);
    $('#con-token').onclick = (ev) => { ev.preventDefault(); pantallaAcceso(); };
  }

  function dialogoContrasena(primeraVez) {
    const d = dialogo(`<h2>${primeraVez ? '¿Entrar con contraseña?' : 'Contraseña del panel'}</h2>
      <p class="sub">${primeraVez ? 'Así, en otros móviles u ordenadores solo tendrás que escribir una contraseña, no el token.' : 'Sirve para entrar al panel desde cualquier dispositivo sin el token.'}
        El token se guarda cifrado con ella: usa una contraseña larga que no uses en otros sitios.</p>
      <label class="campo"><span>Contraseña (mínimo 10 caracteres)</span><input id="p1" type="password" autocomplete="new-password"></label>
      <label class="campo"><span>Repítela</span><input id="p2" type="password" autocomplete="new-password"></label>
      <div class="fila fin"><button class="btn sec" id="p-no">${primeraVez ? 'Ahora no' : 'Cancelar'}</button><button class="btn" id="p-ok">Guardar contraseña</button></div>`);
    $('#p-no', d).onclick = () => { if (primeraVez) local.set('pueblos-sin-clave', '1'); d.remove(); };
    $('#p-ok', d).onclick = async () => {
      const a = $('#p1', d).value, b = $('#p2', d).value;
      if (a.length < 10) { aviso('La contraseña debe tener al menos 10 caracteres.', true); return; }
      if (a !== b) { aviso('Las dos contraseñas no coinciden.', true); return; }
      d.remove();
      espera('Cifrando…');
      try {
        const acceso = await cifrarToken(E.gh.token, E.repo, a);
        await guardar([], [], [], 'Contraseña del panel de gestión', [{ ruta: 'acceso_panel.json', contenido: JSON.stringify(acceso, null, 2) }]);
        E.acceso = acceso;
        aviso('Contraseña guardada. En 1–2 minutos podrás usarla en cualquier dispositivo.');
      } catch (e) { finEspera(); aviso(e.message, true); }
    };
  }

  function pantallaLista() {
    E.editor = null;
    const todos = Object.values(E.pueblos).filter((p) => p.nombre);
    const vis = todos.filter((p) => p.estado !== 'pendiente');
    const pen = todos.filter((p) => p.estado === 'pendiente');
    const sinPropias = vis.filter((p) => !p.fotos.some((f) => !f.credito)).length;
    const lista = (E.vista === 'pendientes' ? pen : vis)
      .filter((p) => !E.filtro || normalizar(`${p.nombre} ${p.provincia} ${p.comunidad}`).includes(normalizar(E.filtro)))
      .sort((a, b) => normalizar(a.nombre).localeCompare(normalizar(b.nombre)));
    const web = `https://${E.repo.split('/')[0]}.github.io/${E.repo.split('/')[1]}/`;
    app().innerHTML = `
      ${cabecera('Mis pueblos', 'panel de gestión', '', `<a class="icono" href="${esc(web)}" target="_blank" rel="noopener" title="Ver mi web" aria-label="Ver mi web" style="text-decoration:none">🌐</a><button class="icono" id="ajustes" title="Ajustes" aria-label="Ajustes">⚙</button>`)}
      <main class="cont">
        <div class="pestanas" role="tablist">
          <button data-v="visitados" aria-pressed="${E.vista === 'visitados'}">🏘 Visitados · ${vis.length}</button>
          <button data-v="pendientes" aria-pressed="${E.vista === 'pendientes'}">📌 Por visitar · ${pen.length}</button>
        </div>
        <input class="buscar" id="buscar" type="search" placeholder="🔎 Buscar pueblo o provincia…" value="${esc(E.filtro)}">
        ${E.vista === 'visitados' && sinPropias ? `<p class="resumen">${sinPropias} ${sinPropias === 1 ? 'pueblo visitado' : 'pueblos visitados'} sin fotos tuyas todavía.</p>` : ''}
        <div class="rejilla">${lista.map(ficha).join('') || `<p class="vacio" style="grid-column:1/-1">${E.filtro ? 'No hay pueblos que coincidan.' :
          E.vista === 'visitados' ? 'Todavía no hay pueblos. Sube las fotos de un viaje o añade uno.' : 'Tu lista de pendientes está vacía.'}</p>`}</div>
      </main>
      <nav class="acciones">
        <button class="btn sec" id="nuevo">＋ Pueblo</button>
        <button class="btn" id="subir">📷 Subir fotos</button>
      </nav>`;
    $$('.pestanas button').forEach((b) => (b.onclick = () => { E.vista = b.dataset.v; pantallaLista(); }));
    $('#buscar').oninput = (ev) => {
      E.filtro = ev.target.value;
      const pos = ev.target.selectionStart;
      pantallaLista();
      const nb = $('#buscar'); nb.focus(); try { nb.setSelectionRange(pos, pos); } catch (e) { /* nada */ }
    };
    $$('.ficha').forEach((f) => (f.onclick = () => abrirEditor(f.dataset.slug)));
    $('#nuevo').onclick = () => dialogoNuevo(E.vista === 'pendientes' ? 'pendiente' : null);
    $('#subir').onclick = () => elegirFotos((files) => subirFotosViaje(files));
    $('#ajustes').onclick = pantallaAjustes;
    pintarAvisoInstalar();
  }

  function ficha(p) {
    const pend = p.estado === 'pendiente';
    const foto = p.portada ? `<img src="${esc(urlFoto(p.slug, p.portada))}" alt="" loading="lazy">` : `<span>${esc(p.nombre.slice(0, 1))}</span>`;
    const ultima = (p.fechas_visita || []).slice(-1)[0];
    const sub = pend ? (p.provincia || 'Por visitar')
      : [p.provincia || p.comunidad, ultima ? fechaCorta(ultima) : '', p.fotos.some((f) => !f.credito) ? '' : '🌐 sin fotos tuyas'].filter(Boolean).join(' · ');
    return `<button class="ficha${pend ? ' pend' : ''}" data-slug="${esc(p.slug)}"><div class="foto">${foto}</div>
      <div class="txt"><b>${esc(p.nombre)}</b><small>${esc(sub)}</small></div></button>`;
  }

  function pantallaAjustes() {
    app().innerHTML = `
      ${cabecera('Ajustes', '', '<button class="icono" id="volver" aria-label="Volver">←</button>')}
      <main class="cont">
        <div class="tarjeta">
          <h2>Conexión</h2>
          <p>Repositorio: <b>${esc(E.repo)}</b> · rama <b>${esc(E.rama)}</b></p>
          <p class="ayuda">Los cambios se guardan en GitHub y la web se actualiza sola en 1–2 minutos.
            El programa de Windows los recibe la próxima vez que lo abras.</p>
          <div class="fila" style="margin-top:12px">
            <button class="btn sec" id="recargar">⟳ Recargar datos</button>
            <button class="btn peligro" id="salir">Cerrar sesión en este navegador</button>
          </div>
        </div>
        <div class="tarjeta">
          <h2>Contraseña</h2>
          <p class="ayuda">${E.acceso ? 'Tienes una contraseña para entrar al panel desde cualquier dispositivo sin el token.' : 'Aún no tienes contraseña: en otros dispositivos te pedirá el token.'}
            Si cambias el token (por ejemplo, al caducar), vuelve a guardar la contraseña aquí.</p>
          <div class="fila" style="margin-top:10px"><button class="btn sec" id="clave">🔑 ${E.acceso ? 'Cambiar la contraseña' : 'Poner contraseña'}</button></div>
        </div>
        <div class="tarjeta">
          <h2>Instalar en el móvil</h2>
          ${INST.instalada() ? '<p class="ayuda">✅ Estás usando el panel instalado.</p>'
            : `<p class="ayuda">Pon el panel en la pantalla de inicio con su propio icono («Gestión») y ábrelo a pantalla completa, como una app.</p>
          <div class="fila" style="margin-top:10px"><button class="btn sec" id="instalar">📲 Instalar el panel</button></div>
          <p class="ayuda" id="instalar-ios" hidden>${INST.ev ? '' : (INST.ios ? AYUDA_IOS
            : 'Abre el menú del navegador (⋮) y elige <b>«Instalar aplicación»</b> o <b>«Añadir a pantalla de inicio»</b>.')}</p>`}
        </div>
        <div class="tarjeta">
          <h2>Fotos</h2>
          <p class="ayuda">Las fotos se reducen y se les quita la ubicación GPS en tu móvil antes de subirlas.
            Las de internet son de Wikimedia Commons y en la web se cita su autor y licencia.</p>
        </div>
      </main>`;
    $('#volver').onclick = pantallaLista;
    $('#recargar').onclick = async () => { await cargarTodo(); pantallaLista(); };
    $('#clave').onclick = () => dialogoContrasena(false);
    if ($('#instalar')) $('#instalar').onclick = () => instalar($('#instalar-ios'));
    $('#salir').onclick = () => {
      if (!confirm('¿Olvidar el token en este navegador?')) return;
      local.del('pueblos-token'); E.gh = null; pantallaAcceso();
    };
  }

  // ------------------------------------------------------------------ editor
  function abrirEditor(slug, empujar) {
    const p = E.pueblos[slug];
    if (!p) { pantallaLista(); return; }
    E.editor = { slug, orig: clonar(p), ed: clonar(p), sel: new Set(), empujado: empujar !== false };
    if (empujar !== false) history.pushState({ slug }, '', `#${encodeURIComponent(slug)}`);
    pintarEditor();
  }

  function diferencias() {
    const { orig, ed } = E.editor;
    const claves = ['nombre', 'provincia', 'comunidad', 'pais', 'lat', 'lon', 'fechas_visita', 'wiki', 'texto_ia', 'notas', 'publicar', 'estado', 'portada'];
    const cambiadas = claves.filter((k) => !igual(orig[k], ed[k]));
    const enOrig = new Set(orig.fotos.map((f) => f.archivo)), enEd = new Set(ed.fotos.map((f) => f.archivo));
    const quitadas = [...enOrig].filter((a) => !enEd.has(a));
    const pies = {};
    for (const f of ed.fotos) { const o = orig.fotos.find((x) => x.archivo === f.archivo); if (o && (o.pie || '') !== (f.pie || '')) pies[f.archivo] = f.pie || ''; }
    return { cambiadas, quitadas, pies, hay: cambiadas.length > 0 || quitadas.length > 0 || Object.keys(pies).length > 0 };
  }
  /* Operación de guardado que aplica lo editado sobre la versión más reciente del pueblo */
  function opEditor(extraFotos, extraFechas, forzarVisitado) {
    const { ed, slug } = E.editor;
    const dif = diferencias();
    return {
      slug,
      aplicar(fresco) {
        const p = fresco || clonar(ed);
        for (const k of dif.cambiadas) p[k] = clonar(ed[k]);
        p.fotos = p.fotos.filter((f) => !dif.quitadas.includes(f.archivo))
          .map((f) => (f.archivo in dif.pies ? Object.assign({}, f, { pie: dif.pies[f.archivo] }) : f));
        const ya = new Set(p.fotos.map((f) => f.original).filter(Boolean));
        for (const f of extraFotos || []) if (!f.original || !ya.has(f.original)) p.fotos.push(f);
        p.fechas_visita = (p.fechas_visita || []).concat(extraFechas || []);
        if (forzarVisitado) p.estado = 'visitado';
        return p;
      },
    };
  }
  function leerFormulario() {
    const ed = E.editor.ed;
    const v = (id) => ($('#' + id) ? $('#' + id).value : '');
    ed.nombre = v('f-nombre').trim();
    ed.provincia = v('f-provincia').trim();
    ed.comunidad = v('f-comunidad').trim();
    ed.fechas_visita = v('f-fechas').split(/[,;]/).map((x) => x.trim()).filter(Boolean);
    const num = (t, antes) => { t = t.replace(',', '.').trim(); if (t === '') return null; return isNaN(+t) ? antes : +t; };
    ed.lat = num(v('f-lat'), ed.lat);
    ed.lon = num(v('f-lon'), ed.lon);
    if ($('#f-publicar')) ed.publicar = $('#f-publicar').checked;
    ed.notas = v('f-notas');
    const extracto = v('f-wiki');
    if ((ed.wiki.extracto || '') !== extracto) ed.wiki = Object.assign({}, ed.wiki, { extracto });
  }

  function pintarEditor() {
    const { ed, sel } = E.editor;
    const pend = ed.estado === 'pendiente';
    const propias = ed.fotos.filter((f) => !f.credito).length;
    app().innerHTML = `
      ${cabecera(ed.nombre || 'Pueblo', [ed.provincia, ed.comunidad].filter(Boolean).join(' · '), '<button class="icono" id="volver" aria-label="Volver">←</button>')}
      <main class="cont">
        <div class="estado" role="group" aria-label="Estado">
          <button data-e="visitado" aria-pressed="${!pend}">✓ Visitado</button>
          <button data-e="pendiente" class="pend" aria-pressed="${pend}">📌 Por visitar</button>
        </div>

        <section class="tarjeta">
          <h2>Fotos <small style="font:500 14px var(--f-texto);color:var(--tinta-2)">${ed.fotos.length}${ed.fotos.length && !propias ? ' · todas de internet' : ''}</small></h2>
          ${sel.size ? `<div class="barra-sel">
            <button class="btn peq sec" id="portada" ${sel.size !== 1 ? 'disabled' : ''}>★ Portada</button>
            <button class="btn peq sec" id="pie" ${sel.size !== 1 ? 'disabled' : ''}>✎ Pie de foto</button>
            <button class="btn peq peligro" id="quitar">Quitar ${sel.size}</button>
            <button class="btn peq fant" id="nosel">Cancelar</button></div>` : ''}
          <div class="galeria">${ed.fotos.map((f) => `
            <button class="miniatura${sel.has(f.archivo) ? ' sel' : ''}" data-a="${esc(f.archivo)}" aria-label="Foto ${esc(f.pie || '')}">
              <img src="${esc(urlFoto(ed.slug, f.archivo))}" alt="" loading="lazy">
              ${f.archivo === ed.portada ? '<span class="marca">★</span>' : ''}${f.credito ? '<span class="web">🌐</span>' : ''}
            </button>`).join('')}</div>
          ${!ed.fotos.length ? `<p class="ayuda">${pend ? 'Puedes poner fotos de internet para tu lista de pendientes.' : '¿Aún no tienes fotos tuyas? Pon alguna de internet mientras tanto.'}</p>` : ''}
          <div class="fila" style="margin-top:8px">
            <button class="btn peq" id="mis-fotos">📷 Mis fotos</button>
            <button class="btn peq sec" id="internet">🌐 Fotos de internet</button>
          </div>
        </section>

        <section class="tarjeta">
          <h2>Datos</h2>
          <label class="campo"><span>Nombre</span><input id="f-nombre" value="${esc(ed.nombre)}"></label>
          <div class="dos">
            <label class="campo"><span>Provincia</span><input id="f-provincia" value="${esc(ed.provincia)}"></label>
            <label class="campo"><span>Comunidad</span><select id="f-comunidad">
              ${(COMUNIDADES.includes(ed.comunidad) || !ed.comunidad ? COMUNIDADES : [ed.comunidad].concat(COMUNIDADES))
                .map((c) => `<option ${c === ed.comunidad ? 'selected' : ''}>${esc(c)}</option>`).join('')}
              ${!ed.comunidad ? '<option value="" selected>—</option>' : ''}</select></label>
          </div>
          <label class="campo" ${pend ? 'hidden' : ''}><span>Fechas de visita</span>
            <input id="f-fechas" value="${esc(ed.fechas_visita.join(', '))}" placeholder="2024-05-12, 2019 (vacío si no lo recuerdas)">
            <span class="ayuda">AAAA-MM-DD, o solo AAAA-MM o AAAA. Separadas por comas.</span></label>
          <div class="fila" ${pend ? 'hidden' : ''} style="margin:-4px 0 10px"><button class="btn peq fant" id="hoy">📅 Añadir hoy</button></div>
          <div class="dos">
            <label class="campo"><span>Latitud</span><input id="f-lat" inputmode="decimal" value="${ed.lat == null ? '' : ed.lat}"></label>
            <label class="campo"><span>Longitud</span><input id="f-lon" inputmode="decimal" value="${ed.lon == null ? '' : ed.lon}"></label>
          </div>
          <div class="fila"><button class="btn peq sec" id="ubicar">🔎 Buscar ubicación</button></div>
          <label class="interruptor"><input type="checkbox" id="f-publicar" ${ed.publicar !== false ? 'checked' : ''}> Publicar en la web</label>
        </section>

        <section class="tarjeta">
          <h2>Mis notas</h2>
          <label class="campo"><textarea id="f-notas" placeholder="Con quién fuiste, qué viste, dónde comiste…">${esc(ed.notas)}</textarea></label>
        </section>

        <section class="tarjeta">
          <h2>Wikipedia</h2>
          <p class="ayuda" style="margin:0 0 8px">${esc([ed.wiki.titulo, ed.wiki.poblacion ? ed.wiki.poblacion.toLocaleString('es-ES') + ' hab.' : '', ed.wiki.altitud != null && ed.wiki.altitud !== '' ? ed.wiki.altitud + ' m' : ''].filter(Boolean).join(' · ') || 'Sin datos todavía')}</p>
          ${ed.wiki.secciones || ed.wiki.que_ver ? `<p class="ayuda" style="margin:0 0 8px">Además: ${[ed.wiki.secciones ? ed.wiki.secciones.map((s) => s.titulo).join(', ') : '', ed.wiki.que_ver ? ed.wiki.que_ver.length + ' lugares que ver' : '', ed.wiki.gentilicio ? 'gentilicio' : '', ed.wiki.patron ? 'patrón' : ''].filter(Boolean).map(esc).join(' · ')}</p>` : ''}
          <label class="campo"><textarea id="f-wiki">${esc(ed.wiki.extracto || '')}</textarea></label>
          <button class="btn peq sec" id="traer-wiki">⬇ Traer de Wikipedia</button>
        </section>

        <button class="btn peligro ancho" id="eliminar" style="margin-top:6px">Eliminar este pueblo</button>
      </main>
      <nav class="acciones"><button class="btn" id="guardar">💾 Guardar</button></nav>`;

    $('#volver').onclick = () => {
      if (E.editor.empujado) { history.back(); return; }
      leerFormulario();
      if (diferencias().hay && !confirm('Tienes cambios sin guardar. ¿Salir sin guardarlos?')) return;
      history.replaceState(null, '', location.pathname + location.search);
      pantallaLista();
    };
    $$('.estado button').forEach((b) => (b.onclick = () => {
      leerFormulario();
      const antes = ed.estado;
      ed.estado = b.dataset.e;
      if (antes === 'pendiente' && ed.estado === 'visitado' && !ed.fechas_visita.length) {
        const f = prompt('¡Enhorabuena! ¿Cuándo lo visitaste? (AAAA-MM-DD, AAAA-MM o AAAA; vacío si no lo recuerdas)', hoy());
        if (f && fechaValida(f.trim())) ed.fechas_visita.push(f.trim());
      }
      pintarEditor();
    }));
    $$('.miniatura').forEach((m) => (m.onclick = () => {
      leerFormulario();
      const a = m.dataset.a;
      if (sel.has(a)) sel.delete(a); else sel.add(a);
      pintarEditor();
    }));
    const portada = $('#portada'); if (portada) portada.onclick = () => { leerFormulario(); ed.portada = [...sel][0]; sel.clear(); pintarEditor(); };
    const pie = $('#pie'); if (pie) pie.onclick = () => {
      leerFormulario();
      const f = ed.fotos.find((x) => x.archivo === [...sel][0]);
      const t = prompt('Pie de foto:', f.pie || '');
      if (t !== null) f.pie = t.trim();
      sel.clear(); pintarEditor();
    };
    const quitar = $('#quitar'); if (quitar) quitar.onclick = () => {
      leerFormulario();
      if (!confirm(`¿Quitar ${sel.size} foto(s) de este pueblo? Se borrarán al guardar.`)) return;
      ed.fotos = ed.fotos.filter((f) => !sel.has(f.archivo)); sel.clear(); pintarEditor();
    };
    const nosel = $('#nosel'); if (nosel) nosel.onclick = () => { leerFormulario(); sel.clear(); pintarEditor(); };
    $('#hoy').onclick = () => { leerFormulario(); if (!ed.fechas_visita.includes(hoy())) ed.fechas_visita.push(hoy()); pintarEditor(); };
    $('#mis-fotos').onclick = () => { leerFormulario(); elegirFotos(anadirMisFotos); };
    $('#internet').onclick = () => { leerFormulario(); dialogoCommons(); };
    $('#ubicar').onclick = () => { leerFormulario(); ubicar(); };
    $('#traer-wiki').onclick = () => { leerFormulario(); traerWiki(); };
    $('#guardar').onclick = () => { leerFormulario(); guardarEditor(); };
    $('#eliminar').onclick = eliminarPueblo;
  }

  async function guardarEditor(silencioso) {
    const { ed, slug } = E.editor;
    if (!ed.nombre) { aviso('El pueblo necesita un nombre.', true); return false; }
    for (const f of ed.fechas_visita) if (!fechaValida(f)) { aviso(`La fecha «${f}» no es válida. Usa AAAA-MM-DD, AAAA-MM o AAAA.`, true); return false; }
    const dif = diferencias();
    if (!dif.hay) { if (!silencioso) aviso('No hay cambios que guardar.'); return true; }
    const borrar = [];
    for (const a of dif.quitadas) borrar.push(`datos/${slug}/fotos/${a}`, `datos/${slug}/mini/${a}`);
    try {
      const res = await guardar([opEditor()], [], borrar.filter((r) => (E.archivos[slug] || []).includes(r)), `${ed.nombre}: cambios desde el panel`);
      const p = res[slug];
      E.editor.orig = clonar(p); E.editor.ed = clonar(p); E.editor.sel.clear();
      pintarEditor();
      aviso('Guardado. La web se actualizará en 1–2 minutos.');
      return true;
    } catch (e) { aviso(e.message, true); return false; }
  }

  async function anadirMisFotos(files) {
    const { ed, slug } = E.editor;
    const ya = new Set(ed.fotos.map((f) => f.original).filter(Boolean));
    const nuevas = [], binarios = [], fechas = [];
    let fallos = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (ya.has(claveOriginal(file))) continue;
      espera(`Preparando fotos (${i + 1} de ${files.length})…`, i / files.length);
      try {
        const meta = await leerMeta(file);
        const { grande, mini } = await prepararFoto(file);
        const nombre = nombreFoto();
        binarios.push({ ruta: `datos/${slug}/fotos/${nombre}`, blob: grande }, { ruta: `datos/${slug}/mini/${nombre}`, blob: mini });
        E.locales[`datos/${slug}/mini/${nombre}`] = URL.createObjectURL(mini);
        E.locales[`datos/${slug}/fotos/${nombre}`] = URL.createObjectURL(grande);
        nuevas.push({ archivo: nombre, fecha: meta.fecha, pie: '', original: claveOriginal(file) });
        if (meta.fecha) fechas.push(meta.fecha);
        if (ed.lat == null && meta.lat != null) { ed.lat = meta.lat; ed.lon = meta.lon; }
      } catch (e) { fallos++; }
    }
    finEspera();
    if (!nuevas.length) { aviso(fallos ? 'No se pudo abrir ninguna foto.' : 'Esas fotos ya estaban.', !!fallos); return; }
    const marcar = ed.estado === 'pendiente' && confirm('Has añadido fotos tuyas. ¿Lo marco como visitado?');
    try {
      const res = await guardar([opEditor(nuevas, ed.estado === 'pendiente' && !marcar ? [] : fechas, marcar)], binarios, [], `${ed.nombre}: ${nuevas.length} fotos desde el panel`);
      const p = res[slug];
      E.editor.orig = clonar(p); E.editor.ed = clonar(p);
      pintarEditor();
      aviso(`Añadidas ${nuevas.length} fotos${fallos ? ` (${fallos} no se pudieron abrir)` : ''}.`);
    } catch (e) { aviso(e.message, true); }
  }

  async function ubicar() {
    const { ed } = E.editor;
    const texto = [ed.nombre, ed.provincia].filter(Boolean).join(', ');
    if (!texto) return;
    espera('Buscando en el mapa…');
    let res;
    try { res = await geoBuscar(texto); } catch (e) { finEspera(); aviso(e.message, true); return; }
    finEspera();
    if (!res.length) { aviso(`No encuentro «${texto}» en el mapa.`, true); return; }
    const r = res.length === 1 ? res[0] : await elegirLugar(res);
    if (!r) return;
    ed.provincia = r.provincia || ed.provincia; ed.comunidad = r.comunidad || ed.comunidad;
    ed.lat = +r.lat.toFixed(6); ed.lon = +r.lon.toFixed(6);
    pintarEditor();
    aviso(`Ubicado en ${ed.provincia}. Recuerda guardar.`);
  }

  async function traerWiki() {
    const { ed } = E.editor;
    if (ed.wiki.extracto && !confirm('Ya hay texto de Wikipedia. ¿Lo sustituyo?')) return;
    espera('Consultando Wikipedia…');
    try {
      const d = await wikiTodo(ed.nombre, ed.provincia, ed.lat, ed.lon);
      finEspera();
      if (!aplicarWiki(ed, d)) { aviso('No he encontrado el artículo en Wikipedia.', true); return; }
      pintarEditor();
      aviso(`Datos de «${d.titulo}». Recuerda guardar.`);
    } catch (e) { finEspera(); aviso(e.message, true); }
  }

  async function eliminarPueblo() {
    const { ed, slug } = E.editor;
    if (!confirm(`¿Eliminar «${ed.nombre}» con todas sus fotos? Desaparecerá de la web.`)) return;
    try {
      const borrar = (E.archivos[slug] || []).slice();
      if (!borrar.includes(`datos/${slug}/pueblo.json`)) borrar.push(`datos/${slug}/pueblo.json`);
      await guardar([], [], borrar, `Eliminar ${ed.nombre} desde el panel`);
      delete E.pueblos[slug]; delete E.archivos[slug];
      E.editor = null;
      history.replaceState(null, '', location.pathname + location.search);
      pantallaLista();
      aviso('Pueblo eliminado.');
    } catch (e) { aviso(e.message, true); }
  }

  // ------------------------------------------------------------------ diálogos
  function dialogo(html) {
    const velo = document.createElement('div');
    velo.className = 'velo';
    velo.innerHTML = `<div class="dialogo" role="dialog" aria-modal="true">${html}</div>`;
    document.body.appendChild(velo);
    velo.addEventListener('click', (ev) => { if (ev.target === velo) velo.remove(); });
    return velo;
  }

  function elegirLugar(res) {
    return new Promise((ok) => {
      const d = dialogo(`<h2>¿Cuál es?</h2><p class="sub">Hay varios lugares con ese nombre.</p>
        <div class="lista-opciones">${res.map((r, i) => `<button data-i="${i}"><b>${esc(r.nombre)}</b><small>${esc(r.descripcion)}</small></button>`).join('')}</div>
        <button class="btn sec ancho" id="cancelar">Cancelar</button>`);
      $$('.lista-opciones button', d).forEach((b) => (b.onclick = () => { d.remove(); ok(res[+b.dataset.i]); }));
      $('#cancelar', d).onclick = () => { d.remove(); ok(null); };
    });
  }

  function elegirFotos(cb) {
    const input = $('#selector-fotos');
    input.value = '';
    input.onchange = () => { const files = Array.from(input.files || []); if (files.length) cb(files); };
    input.click();
  }

  /* Pueblo nuevo: nombre → lugar → ¿visitado o pendiente? (y cuándo) → Wikipedia → fotos de internet */
  function dialogoNuevo(estadoFijo) {
    const d = dialogo(`<h2>Nuevo pueblo</h2>
      <label class="campo"><span>Nombre del pueblo</span><input id="n-nombre" placeholder="Por ejemplo: Albarracín" autocomplete="off"></label>
      <div class="fila fin"><button class="btn sec" id="n-cancelar">Cancelar</button><button class="btn" id="n-buscar">Buscar</button></div>`);
    const input = $('#n-nombre', d);
    setTimeout(() => input.focus(), 50);
    $('#n-cancelar', d).onclick = () => d.remove();
    const buscar = async () => {
      const nombre = input.value.trim();
      if (!nombre) return;
      espera('Buscando en el mapa…');
      let res = [];
      try { res = await geoBuscar(nombre); } catch (e) { aviso(e.message, true); }
      finEspera();
      d.remove();
      let lugar = null;
      if (res.length === 1) lugar = res[0];
      else if (res.length > 1) lugar = await elegirLugar(res);
      if (!lugar && res.length) return;
      if (!lugar) lugar = { nombre, provincia: '', comunidad: '', pais: '', lat: null, lon: null };
      lugar.nombre = lugar.nombre && normalizar(lugar.nombre).includes(normalizar(nombre)) ? lugar.nombre : nombre;
      const existente = buscarPueblo(lugar.nombre, lugar.provincia);
      if (existente) { aviso(`«${existente.nombre}» ya está en tu lista.`); abrirEditor(existente.slug); return; }
      preguntarEstado(lugar, estadoFijo);
    };
    $('#n-buscar', d).onclick = buscar;
    input.onkeydown = (ev) => { if (ev.key === 'Enter') buscar(); };
  }

  function preguntarEstado(lugar, estadoFijo) {
    const d = dialogo(`<h2>${esc(lugar.nombre)}</h2>
      <p class="sub">${esc([lugar.provincia, lugar.comunidad].filter(Boolean).join(' · ') || 'Sin ubicación')}</p>
      <div class="estado" role="group">
        <button data-e="visitado" aria-pressed="${estadoFijo !== 'pendiente'}">✓ Ya lo visité</button>
        <button data-e="pendiente" class="pend" aria-pressed="${estadoFijo === 'pendiente'}">📌 Quiero visitarlo</button>
      </div>
      <div id="n-cuando" ${estadoFijo === 'pendiente' ? 'hidden' : ''}>
        <label class="campo"><span>¿Cuándo? (opcional)</span><input id="n-fecha" placeholder="2024-05-12, 2024-05 o 2019" inputmode="numeric"></label>
        <p class="ayuda">Si no tienes fotos tuyas, no pasa nada: podrás poner fotos de internet.</p>
      </div>
      <label class="interruptor"><input type="checkbox" id="n-wiki" checked> Traer datos de Wikipedia</label>
      <div class="fila fin" style="margin-top:10px"><button class="btn sec" id="n-cancelar">Cancelar</button><button class="btn" id="n-crear">Añadir</button></div>`);
    let estado = estadoFijo === 'pendiente' ? 'pendiente' : 'visitado';
    $$('.estado button', d).forEach((b) => (b.onclick = () => {
      estado = b.dataset.e;
      $$('.estado button', d).forEach((x) => x.setAttribute('aria-pressed', x === b));
      $('#n-cuando', d).hidden = estado === 'pendiente';
    }));
    $('#n-cancelar', d).onclick = () => d.remove();
    $('#n-crear', d).onclick = async () => {
      const fecha = $('#n-fecha', d).value.trim();
      if (estado === 'visitado' && fecha && !fechaValida(fecha)) { aviso('Escribe la fecha como AAAA-MM-DD, AAAA-MM o AAAA.', true); return; }
      const conWiki = $('#n-wiki', d).checked;
      d.remove();
      const p = puebloVacio(lugar.nombre);
      Object.assign(p, { provincia: lugar.provincia, comunidad: lugar.comunidad, pais: lugar.pais || 'España', estado });
      if (lugar.lat != null) { p.lat = +lugar.lat.toFixed(6); p.lon = +lugar.lon.toFixed(6); }
      if (estado === 'visitado' && fecha) p.fechas_visita = [fecha];
      if (conWiki) {
        espera('Consultando Wikipedia…');
        try { aplicarWiki(p, await wikiTodo(p.nombre, p.provincia, p.lat, p.lon)); } catch (e) { console.warn(e); }
        finEspera();
      }
      const slug = slugLibre(p.nombre, p.provincia);
      p.slug = slug;
      try {
        await guardar([{ slug, aplicar: (fresco) => fresco || p }], [], [], `Nuevo pueblo: ${p.nombre}`);
        abrirEditor(slug);
        ofrecerFotos(p, estado);
      } catch (e) { aviso(e.message, true); }
    };
  }

  function ofrecerFotos(p, estado) {
    const d = dialogo(`<h2>«${esc(p.nombre)}» añadido</h2>
      <p class="sub">${estado === 'visitado' ? '¿Le pones ya alguna foto? Si no tienes fotos tuyas, puedes usar fotos libres de internet.'
        : 'Puedes ponerle fotos de internet para tu lista de pendientes.'}</p>
      <div class="lista-opciones">
        <button id="o-internet">🌐 <b>Fotos de internet</b><small>Fotos libres de Wikimedia Commons, con su autor citado</small></button>
        ${estado === 'visitado' ? '<button id="o-mias">📷 <b>Mis fotos</b><small>Desde la galería del móvil</small></button>' : ''}
      </div>
      <button class="btn sec ancho" id="o-luego">Más tarde</button>`);
    $('#o-internet', d).onclick = () => { d.remove(); dialogoCommons(); };
    const mias = $('#o-mias', d); if (mias) mias.onclick = () => { d.remove(); elegirFotos(anadirMisFotos); };
    $('#o-luego', d).onclick = () => d.remove();
  }

  async function dialogoCommons() {
    const { ed, slug } = E.editor;
    espera('Buscando fotos libres en Wikimedia Commons…');
    let items = [];
    try { items = await commonsBuscar(ed); } catch (e) { aviso(e.message, true); }
    finEspera();
    const ya = new Set(ed.fotos.map((f) => f.original));
    items = items.filter((it) => !ya.has(it.pagina));
    if (!items.length) { aviso('No he encontrado fotos libres de este pueblo. Revisa el nombre y la ubicación.', true); return; }
    const d = dialogo(`<h2>Fotos de internet</h2>
      <p class="sub">Fotos de uso libre de Wikimedia Commons. En la web se citará su autor y licencia. Revisa que sean del pueblo.</p>
      <div class="commons">${items.map((it, i) => `<label><input type="checkbox" data-i="${i}"><img src="${esc(it.miniatura)}" alt="" loading="lazy">
        <small>${esc(it.autor)} · ${esc(it.licencia)}</small></label>`).join('')}</div>
      <div class="fila fin"><button class="btn sec" id="c-cancelar">Cancelar</button><button class="btn" id="c-anadir">Añadir las marcadas</button></div>`);
    $('#c-cancelar', d).onclick = () => d.remove();
    $('#c-anadir', d).onclick = async () => {
      const elegidas = $$('.commons input:checked', d).map((x) => items[+x.dataset.i]);
      if (!elegidas.length) { aviso('No has marcado ninguna foto.'); return; }
      d.remove();
      const nuevas = [], binarios = [];
      let fallos = 0;
      try {
        espera('Descargando fotos…');
        const grandes = {};
        for (let i = 0; i < elegidas.length; i += 40) {
          const lote = elegidas.slice(i, i + 40);
          for (const it of await commonsConsulta({ titles: lote.map((x) => x.titulo).join('|') }, 1600)) grandes[it.titulo] = it.miniatura;
        }
        for (let i = 0; i < elegidas.length; i++) {
          const it = elegidas[i];
          espera(`Preparando fotos (${i + 1} de ${elegidas.length})…`, i / elegidas.length);
          try {
            const r = await fetch(grandes[it.titulo] || it.miniatura);
            if (!r.ok) throw new Error(r.status);
            const { grande, mini } = await prepararFoto(await r.blob());
            const nombre = nombreFoto();
            binarios.push({ ruta: `datos/${slug}/fotos/${nombre}`, blob: grande }, { ruta: `datos/${slug}/mini/${nombre}`, blob: mini });
            E.locales[`datos/${slug}/mini/${nombre}`] = URL.createObjectURL(mini);
            E.locales[`datos/${slug}/fotos/${nombre}`] = URL.createObjectURL(grande);
            nuevas.push({ archivo: nombre, fecha: '', pie: '', original: it.pagina,
              credito: { autor: it.autor, licencia: it.licencia, url_licencia: it.url_licencia, fuente: it.pagina } });
          } catch (e) { fallos++; }
        }
      } finally { finEspera(); }
      if (!nuevas.length) { aviso('No se pudo descargar ninguna foto.', true); return; }
      try {
        const res = await guardar([opEditor(nuevas)], binarios, [], `${ed.nombre}: ${nuevas.length} fotos de Wikimedia Commons`);
        const p = res[slug];
        E.editor.orig = clonar(p); E.editor.ed = clonar(p);
        pintarEditor();
        aviso(`Añadidas ${nuevas.length} fotos de internet${fallos ? ` (${fallos} fallaron)` : ''}.`);
      } catch (e) { aviso(e.message, true); }
    };
  }

  // ------------------------------------------------------------------ subir fotos de un viaje
  async function subirFotosViaje(files) {
    const metas = [];
    for (let i = 0; i < files.length; i++) {
      espera(`Leyendo las fotos (${i + 1} de ${files.length})…`, i / files.length);
      metas.push(await leerMeta(files[i]));
    }
    const grupos = new Map(), conHora = [], sinGps = [];
    const conGps = metas.filter((m) => m.lat != null);
    let n = 0;
    for (const m of metas) {
      if (m.lat == null) { sinGps.push(m); continue; }
      espera(`Buscando el pueblo de cada foto (${++n} de ${conGps.length})…`, n / conGps.length);
      let info = null;
      try { info = await geoInverso(m.lat, m.lon); } catch (e) { console.warn(e); }
      if (!info || !info.nombre) { sinGps.push(m); continue; }
      const clave = normalizar(info.nombre) + '|' + normalizar(info.provincia);
      if (!grupos.has(clave)) grupos.set(clave, { clave, info, fotos: [], lats: [], lons: [], fechas: new Set(), porHora: 0 });
      const g = grupos.get(clave);
      g.fotos.push(m); g.lats.push(m.lat); g.lons.push(m.lon);
      if (m.fecha) g.fechas.add(m.fecha);
      if (m.momento) conHora.push({ momento: m.momento, clave });
    }
    const resto = [];
    let porHora = 0;
    for (const m of sinGps) {
      let destino = null;
      if (m.momento && conHora.length) {
        const cerca = conHora.reduce((a, b) => (Math.abs(b.momento - m.momento) < Math.abs(a.momento - m.momento) ? b : a));
        if (Math.abs(cerca.momento - m.momento) <= MARGEN_HORAS * 3600e3) destino = cerca.clave;
      }
      if (destino) { const g = grupos.get(destino); g.fotos.push(m); g.porHora++; if (m.fecha) g.fechas.add(m.fecha); porHora++; } else resto.push(m);
    }
    finEspera();
    confirmarViaje([...grupos.values()].sort((a, b) => b.fotos.length - a.fotos.length), resto, porHora);
  }

  function confirmarViaje(grupos, resto, porHora) {
    const existentes = Object.values(E.pueblos).sort((a, b) => normalizar(a.nombre).localeCompare(normalizar(b.nombre)));
    const d = dialogo(`<h2>Fotos del viaje</h2>
      ${grupos.length ? '<p class="sub">Pueblos encontrados por el GPS de las fotos. Marca los que quieras añadir:</p>' : '<p class="sub">Ninguna foto tiene ubicación GPS.</p>'}
      ${grupos.map((g, i) => {
        const ex = buscarPueblo(g.info.nombre, g.info.provincia);
        const nota = ex && ex.estado === 'pendiente' ? '<span class="pend-ok">✓ ¡estaba en tu lista de pendientes!</span>' : ex ? 'ya existe: se añaden las fotos' : 'nuevo';
        return `<label class="grupo"><input type="checkbox" data-g="${i}" checked><span><b>${esc(g.info.nombre)}</b> · ${esc(g.info.provincia)}
          <small>${g.fotos.length} fotos${g.porHora ? ` (${g.porHora} sin GPS, por la hora)` : ''} · ${esc([...g.fechas].sort().join(', ') || 'sin fecha')} · ${nota}</small></span></label>`;
      }).join('')}
      ${porHora ? `<p class="ayuda">${porHora} fotos sin GPS se han colocado por la hora en que se hicieron.</p>` : ''}
      ${resto.length ? `<div class="tarjeta" style="margin-top:10px"><b>${resto.length} fotos sin ubicación</b>
        <label class="campo" style="margin-top:8px"><span>¿A qué pueblo las añado?</span><select id="v-resto">
          <option value="">No añadirlas</option>
          ${grupos.map((g, i) => `<option value="g:${i}">${esc(g.info.nombre)} (encontrado ahora)</option>`).join('')}
          ${existentes.map((p) => `<option value="p:${esc(p.slug)}">${esc(p.nombre)} (${esc(p.provincia || 'sin provincia')})</option>`).join('')}
          <option value="nuevo" ${grupos.length ? '' : 'selected'}>A un pueblo nuevo…</option></select></label>
        <label class="campo" id="v-nuevo-c" ${grupos.length ? 'hidden' : ''}><span>Nombre del pueblo nuevo</span><input id="v-nuevo"></label></div>` : ''}
      <label class="interruptor"><input type="checkbox" id="v-wiki" checked> Traer datos de Wikipedia de los pueblos nuevos</label>
      <div class="fila fin" style="margin-top:10px"><button class="btn sec" id="v-cancelar">Cancelar</button><button class="btn" id="v-ok">Añadir</button></div>`);
    const sel = $('#v-resto', d);
    if (sel) sel.onchange = () => { $('#v-nuevo-c', d).hidden = sel.value !== 'nuevo'; };
    $('#v-cancelar', d).onclick = () => d.remove();
    $('#v-ok', d).onclick = () => {
      const elegidos = $$('input[data-g]', d).filter((x) => x.checked).map((x) => grupos[+x.dataset.g]);
      let destinoResto = null;
      if (resto.length && sel && sel.value) {
        if (sel.value === 'nuevo') {
          const nombre = $('#v-nuevo', d).value.trim();
          if (!nombre) { aviso('Escribe el nombre del pueblo nuevo.', true); return; }
          destinoResto = { tipo: 'nuevo', nombre };
        } else if (sel.value.startsWith('g:')) {
          const g = grupos[+sel.value.slice(2)];
          if (!elegidos.includes(g)) elegidos.push(g);
          g.fotos.push(...resto);
        } else destinoResto = { tipo: 'existente', slug: sel.value.slice(2) };
      }
      const conWiki = $('#v-wiki', d).checked;
      d.remove();
      if (elegidos.length || destinoResto) aplicarViaje(elegidos, destinoResto, resto, conWiki);
    };
  }

  async function aplicarViaje(grupos, destinoResto, resto, conWiki) {
    const destinos = [];  // {slug, nuevoP|null, metas}
    const reservados = new Set();
    try {
      for (const g of grupos) {
        const ex = buscarPueblo(g.info.nombre, g.info.provincia);
        if (ex) { destinos.push({ slug: ex.slug, nuevo: null, metas: g.fotos }); continue; }
        const p = puebloVacio(g.info.nombre);
        Object.assign(p, { provincia: g.info.provincia, comunidad: g.info.comunidad, pais: g.info.pais || 'España' });
        p.lat = +(g.lats.reduce((a, b) => a + b, 0) / g.lats.length).toFixed(6);
        p.lon = +(g.lons.reduce((a, b) => a + b, 0) / g.lons.length).toFixed(6);
        const slug = slugLibre(p.nombre, p.provincia, reservados);
        reservados.add(slug);
        destinos.push({ slug, nuevo: p, metas: g.fotos });
      }
      if (destinoResto && destinoResto.tipo === 'existente') destinos.push({ slug: destinoResto.slug, nuevo: null, metas: resto });
      if (destinoResto && destinoResto.tipo === 'nuevo') {
        const ex = buscarPueblo(destinoResto.nombre);
        if (ex) destinos.push({ slug: ex.slug, nuevo: null, metas: resto });
        else {
          const p = puebloVacio(destinoResto.nombre);
          espera('Buscando el pueblo en el mapa…');
          try {
            const r = await geoBuscar(destinoResto.nombre);
            const lugar = r.find((x) => x.pais === 'España') || r[0];
            if (lugar) Object.assign(p, { provincia: lugar.provincia, comunidad: lugar.comunidad, lat: +lugar.lat.toFixed(6), lon: +lugar.lon.toFixed(6) });
          } catch (e) { console.warn(e); }
          const slug = slugLibre(p.nombre, p.provincia, reservados);
          reservados.add(slug);
          destinos.push({ slug, nuevo: p, metas: resto });
        }
      }
      if (conWiki) {
        for (const dst of destinos.filter((x) => x.nuevo)) {
          espera(`Wikipedia: ${dst.nuevo.nombre}…`);
          try { aplicarWiki(dst.nuevo, await wikiTodo(dst.nuevo.nombre, dst.nuevo.provincia, dst.nuevo.lat, dst.nuevo.lon)); } catch (e) { console.warn(e); }
        }
      }
      const binarios = [];
      const total = destinos.reduce((a, x) => a + x.metas.length, 0);
      let hechas = 0, fallos = 0;
      for (const dst of destinos) {
        dst.entradas = []; dst.fechas = [];
        const ya = new Set(((E.pueblos[dst.slug] || {}).fotos || []).map((f) => f.original));
        for (const m of dst.metas) {
          espera(`Preparando fotos (${++hechas} de ${total})…`, hechas / total);
          if (ya.has(claveOriginal(m.archivo))) continue;
          try {
            const { grande, mini } = await prepararFoto(m.archivo);
            const nombre = nombreFoto();
            binarios.push({ ruta: `datos/${dst.slug}/fotos/${nombre}`, blob: grande }, { ruta: `datos/${dst.slug}/mini/${nombre}`, blob: mini });
            E.locales[`datos/${dst.slug}/mini/${nombre}`] = URL.createObjectURL(mini);
            E.locales[`datos/${dst.slug}/fotos/${nombre}`] = URL.createObjectURL(grande);
            dst.entradas.push({ archivo: nombre, fecha: m.fecha, pie: '', original: claveOriginal(m.archivo) });
            if (m.fecha) dst.fechas.push(m.fecha);
            ya.add(claveOriginal(m.archivo));
          } catch (e) { fallos++; }
        }
      }
      finEspera();
      const cumplidos = [];
      const ops = destinos.filter((x) => x.entradas.length || x.nuevo).map((dst) => ({
        slug: dst.slug,
        aplicar(fresco) {
          const p = fresco || clonar(dst.nuevo || puebloVacio(dst.slug));
          if (p.estado === 'pendiente' && dst.entradas.length) { p.estado = 'visitado'; if (!cumplidos.includes(p.nombre)) cumplidos.push(p.nombre); }
          const ya2 = new Set(p.fotos.map((f) => f.original).filter(Boolean));
          for (const f of dst.entradas) if (!ya2.has(f.original)) p.fotos.push(f);
          p.fechas_visita = (p.fechas_visita || []).concat(dst.fechas);
          return p;
        },
      }));
      if (!ops.length) { aviso(fallos ? 'No se pudo abrir ninguna foto.' : 'Esas fotos ya estaban subidas.', !!fallos); return; }
      await guardar(ops, binarios, [], `Fotos de viaje desde el panel (${ops.length} pueblos)`);
      E.vista = 'visitados';
      pantallaLista();
      aviso(cumplidos.length ? `🎉 ¡Tachado de pendientes: ${cumplidos.join(', ')}!` : `Listo: ${ops.length} ${ops.length === 1 ? 'pueblo actualizado' : 'pueblos actualizados'}.`);
    } catch (e) { finEspera(); aviso(e.message, true); }
  }

  // ------------------------------------------------------------------ inicio
  async function iniciar() {
    try {
      await cargarTodo();
    } catch (e) { aviso(e.message, true); if (/token/i.test(e.message)) { pantallaAcceso(e.message); return; } }
    const slug = decodeURIComponent(location.hash.slice(1));
    if (slug && E.pueblos[slug]) abrirEditor(slug, false); else pantallaLista();
  }

  window.addEventListener('popstate', () => {
    if (!E.gh) return;
    if (E.editor) {
      leerFormulario();
      if (diferencias().hay && !confirm('Tienes cambios sin guardar. ¿Salir sin guardarlos?')) {
        history.pushState({ slug: E.editor.slug }, '', `#${encodeURIComponent(E.editor.slug)}`);
        return;
      }
    }
    const slug = decodeURIComponent(location.hash.slice(1));
    if (slug && E.pueblos[slug]) abrirEditor(slug, false); else pantallaLista();
  });
  window.addEventListener('beforeunload', (ev) => {
    if (E.editor) { try { leerFormulario(); } catch (e) { /* nada */ } if (diferencias().hay) { ev.preventDefault(); ev.returnValue = ''; } }
  });

  async function arrancar() {
    if ('serviceWorker' in navigator && /^https?:/.test(location.protocol)) navigator.serviceWorker.register('sw.js').catch(() => {});
    let cfg = {};
    try { cfg = await (await fetch('config.json', { cache: 'no-store' })).json(); } catch (e) { /* sin config */ }
    const deducido = location.hostname.endsWith('.github.io')
      ? `${location.hostname.split('.')[0]}/${location.pathname.split('/').filter(Boolean)[0] || ''}` : '';
    E.repo = local.get('pueblos-repo') || cfg.repo || deducido;
    E.rama = cfg.rama || 'main';
    try {
      const r = await fetch('acceso.json', { cache: 'no-store' });
      if (r.ok) E.acceso = await r.json();
    } catch (e) { /* sin contraseña */ }
    const token = local.get('pueblos-token');
    if (!token || !E.repo) { if (E.acceso && E.acceso.datos) pantallaContrasena(E.acceso); else pantallaAcceso(); return; }
    E.gh = new GitHub(token, E.repo, E.rama);
    await iniciar();
  }
  window.PUEBLOS_PANEL = { E, normalizar, slugify, fechaBonita };
  arrancar();
})();
