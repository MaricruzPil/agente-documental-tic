import {ApiClient} from './api.js';

const api = new ApiClient();
const el = id => document.getElementById(id);
let askRequestId = 0;

const msg = (text, danger = false) => {
  const box = el('message');
  box.textContent = text;
  box.className = 'status-message ' + (danger ? 'text-danger' : 'text-secondary');
};

function linkFor(source) {
  if (!source.url) return null;
  try {
    const u = new URL(source.url);
    if (u.protocol === 'https:' && ['drive.google.com', 'docs.google.com'].includes(u.hostname)) return u.href;
  } catch (_) {}
  return null;
}

function previewUrlFor(href) {
  try {
    const u = new URL(href);
    if (u.hostname === 'drive.google.com') {
      const match = u.pathname.match(/\/file\/d\/([^/]+)/);
      if (match) return `https://drive.google.com/file/d/${match[1]}/preview`;
    }
    if (u.hostname === 'docs.google.com') return u.href;
  } catch (_) {}
  return null;
}

function setLoading(button, loading) {
  button.disabled = loading;
  button.classList.toggle('loading', loading);
}

function pulse(node) {
  node.classList.remove('updated');
  void node.offsetWidth;
  node.classList.add('updated');
}

function setPreview(source, originNode = null) {
  const state = el('preview-state');
  const frame = el('preview-frame');
  const open = el('preview-open');
  const href = linkFor(source);
  const preview = href ? previewUrlFor(href) : null;

  document.querySelectorAll('.doc-item.selected').forEach(item => item.classList.remove('selected'));
  if (originNode) originNode.classList.add('selected');

  if (href) {
    open.href = href;
    open.classList.remove('disabled');
    open.setAttribute('aria-disabled', 'false');
  } else {
    open.href = '#';
    open.classList.add('disabled');
    open.setAttribute('aria-disabled', 'true');
  }

  if (!preview) {
    frame.removeAttribute('src');
    frame.classList.remove('active');
    state.style.display = 'grid';
    state.textContent = href
      ? 'No hay una URL compatible para incrustar este documento. Puedes abrir el archivo original.'
      : 'Este documento no incluye una URL valida de Google Drive o Docs.';
    return;
  }

  frame.src = preview;
  frame.classList.add('active');
  state.style.display = 'none';
}

function clearPreview() {
  const state = el('preview-state');
  const frame = el('preview-frame');
  const open = el('preview-open');

  document.querySelectorAll('.doc-item.selected').forEach(item => item.classList.remove('selected'));
  frame.removeAttribute('src');
  frame.classList.remove('active');
  state.style.display = 'grid';
  state.textContent = 'Selecciona un documento o una fuente verificable para previsualizarlo.';
  open.removeAttribute('href');
  open.classList.add('disabled');
  open.setAttribute('aria-disabled', 'true');
}

function sourceItem(source) {
  const li = document.createElement('li');
  li.className = 'list-group-item';
  const href = linkFor(source);

  if (href) {
    const a = document.createElement('a');
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener noreferrer';
    a.textContent = source.name;
    a.title = source.name;
    li.append(a);

    const previewButton = document.createElement('button');
    previewButton.type = 'button';
    previewButton.className = 'btn btn-ghost';
    previewButton.textContent = 'Vista';
    previewButton.addEventListener('click', () => setPreview(source));
    li.append(previewButton);
  } else {
    li.textContent = source.name;
  }

  return li;
}

async function loadDocuments() {
  const r = await api.documents();
  el('doc-count').textContent = r.indexed;
  const box = el('documents');
  box.replaceChildren();

  if (!r.documents.length) {
    box.textContent = 'Aun no hay documentos indexados.';
    return;
  }

  for (const d of r.documents) {
    const div = document.createElement('div');
    div.className = 'doc-item';
    const a = document.createElement('a');
    a.className = 'doc-link';
    a.title = d.name;
    a.setAttribute('aria-label', `Abrir ${d.name}`);
    const name = document.createElement('span');
    name.className = 'doc-name';
    name.textContent = d.name;
    name.title = d.name;
    const action = document.createElement('span');
    action.className = 'open-chip';
    action.textContent = 'Abrir';
    a.append(name, action);
    const href = linkFor(d);

    if (href) {
      a.href = href;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      div.addEventListener('click', event => {
        if (event.target === a) return;
        setPreview(d, div);
      });
      div.tabIndex = 0;
      div.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          setPreview(d, div);
        }
      });
    } else {
      a.removeAttribute('href');
    }

    div.append(a);
    box.append(div);
  }
}

async function ask() {
  const q = el('question').value.trim();
  if (q.length < 3) {
    msg('Escribe una pregunta de al menos 3 caracteres.', true);
    return;
  }

  const askButton = el('ask');
  const currentRequestId = ++askRequestId;
  clearPreview();
  setLoading(askButton, true);
  msg('Consultando al agente...');

  try {
    const data = await api.ask(q, el('use-search').checked);
    if (currentRequestId !== askRequestId) return;
    const answer = el('answer');
    answer.textContent = data.answer || 'Sin respuesta.';
    pulse(answer);

    const src = el('sources');
    src.replaceChildren();

    for (const source of data.sources) {
      src.append(sourceItem(source));
    }

    if (data.clarification_request) {
      const li = document.createElement('li');
      li.className = 'list-group-item text-secondary';
      li.textContent = 'Aclaracion requerida antes de consultar documentos.';
      src.append(li);
    } else if (!data.sources.length) {
      const li = document.createElement('li');
      li.className = 'list-group-item text-secondary';
      li.textContent = 'No se encontraron fuentes verificables para esta respuesta.';
      src.append(li);
    }

    pulse(src);
    msg('Consulta finalizada.');
  } catch (e) {
    if (currentRequestId !== askRequestId) return;
    msg(e.message, true);
  } finally {
    if (currentRequestId === askRequestId) setLoading(askButton, false);
  }
}

async function sync() {
  if (!confirm('¿Sincronizar archivos de la carpeta autorizada de Google Drive?')) return;

  const syncButton = el('sync');
  setLoading(syncButton, true);
  msg('Sincronizando documentos...');

  try {
    const r = await api.sync();
    await loadDocuments();
    msg(`Sincronizacion: ${r.stats.added} nuevos, ${r.stats.updated} actualizados, ${r.stats.removed} eliminados, ${r.stats.unchanged} sin cambios. Errores: ${r.stats.errors.length}.`);
  } catch (e) {
    msg(e.message, true);
  } finally {
    setLoading(syncButton, false);
  }
}

function setupNavigation() {
  const navLinks = [...document.querySelectorAll('.nav-pill')];
  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      navLinks.forEach(item => item.classList.remove('active'));
      link.classList.add('active');
    });
  });
}

el('ask').addEventListener('click', ask);
el('sync').addEventListener('click', sync);
el('question').addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) ask();
});

setupNavigation();

api.health()
  .then(r => {
    el('health').textContent = r.configured ? 'Servidor local listo' : 'Configuracion pendiente';
  })
  .catch(() => {
    el('health').textContent = 'Sin conexion';
  });

loadDocuments().catch(e => msg(e.message, true));
