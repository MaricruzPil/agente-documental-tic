# Archivo TIC IA

Agente documental académico para consultar documentos autorizados mediante FastAPI, Google Drive OAuth, OpenAI Vector Store y recuperación aumentada con generación (RAG).

Aplicación pública: <https://agente-documental-tic-one.vercel.app/>

## Funcionalidades

- Biblioteca de documentos indexados.
- Preguntas documentales en español.
- Evaluación semántica de claridad antes de buscar.
- Recuperación de fragmentos desde OpenAI Vector Store.
- Respuestas fundamentadas en evidencia recuperada.
- Fuentes verificables relacionadas con los documentos utilizados.
- Solicitudes de aclaración para preguntas sin referente suficiente.
- Vista previa y apertura de PDF mediante enlaces públicos de Google Drive.
- Sincronización de Google Drive disponible únicamente en localhost.

## Tecnologías

- Python 3.11 o posterior.
- FastAPI y Uvicorn.
- Pydantic para validación de solicitudes.
- Google Drive API y OAuth Desktop para el entorno local.
- OpenAI Responses API y Vector Stores para RAG.
- HTML, CSS y JavaScript para el frontend.
- Pytest y TestClient para pruebas automatizadas.
- Vercel Python Runtime para producción.

## Arquitectura

`run_local.py` es el lanzador de desarrollo. Importa la aplicación ASGI desde `app.main` y solo inicia Uvicorn cuando se ejecuta directamente.

`app/main.py` define la aplicación FastAPI y las rutas `/`, `/assets`, `/api/health`, `/api/documents`, `/api/ask` y `/api/sync`.

`app/services/drive_service.py` gestiona OAuth local, lectura de la carpeta de Drive y descarga de documentos.

`app/services/sync_service.py` compara Drive con el manifiesto local, sube o actualiza archivos en el Vector Store y retira documentos eliminados.

`app/services/agent_service.py` evalúa claridad, busca evidencia, genera respuestas documentales y resuelve fuentes mediante el inventario disponible.

En localhost, el inventario se lee desde `data/manifest.json`. En producción, se lee exclusivamente desde `DOCUMENT_INVENTORY_JSON`.

## Estructura principal

```text
.
├── app/
│   ├── core/config.py          Configuración y variables de entorno
│   ├── main.py                 Aplicación FastAPI ASGI
│   ├── models/documento.py     Esquemas de solicitudes y respuestas
│   └── services/
│       ├── agent_service.py    Evaluación, RAG y fuentes
│       ├── drive_service.py    OAuth y lectura de Google Drive
│       └── sync_service.py     Sincronización e inventario local
├── assets/
│   ├── css/styles.css          Estilos del frontend
│   └── js/                     Cliente API e interacción de la interfaz
├── data/                       Datos locales ignorados por Git
│   └── manifest.json            Inventario local del Vector Store
├── tests/test_app.py            Pruebas automatizadas
├── index.html                   Interfaz web
├── run_local.py                 Lanzador local
├── requirements.txt             Dependencias Python
└── .env.example                 Plantilla sin secretos
```

## Requisitos locales

Se necesita Python, Git, una cuenta de OpenAI con acceso a la API, un proyecto de Google Cloud con Drive API habilitada y una carpeta de Drive con documentos autorizados.

No se deben incluir claves, tokens ni documentos privados en GitHub.

## Instalación en Windows

Desde PowerShell, en la raíz del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

`requirements.txt` incluye dependencias de ejecución y de pruebas para mantener una instalación reproducible del proyecto.

## Variables locales

Edita `.env` solo en la máquina local. La plantilla contiene nombres y valores de ejemplo:

| Variable | Uso local |
|---|---|
| `APP_ENV` | Debe ser `local`. |
| `SYNC_ENABLED` | `true` permite la sincronización local. |
| `OPENAI_API_KEY` | Clave privada del backend. |
| `OPENAI_MODEL` | Modelo utilizado por el agente. |
| `GOOGLE_DRIVE_FOLDER_ID` | Carpeta de Drive autorizada. |
| `VECTOR_STORE_ID` | Vector Store existente; puede dejarse vacío en la primera sincronización. |
| `LOCAL_ADMIN_KEY` | Clave administrativa opcional para `/api/sync`. |
| `OPENAI_TIMEOUT_SECONDS` | Timeout del cliente OpenAI, entre 1 y 120 segundos. |
| `PUBLIC_ASK_ENABLED` | En localhost queda habilitado por la configuración local. |
| `DOCUMENT_INVENTORY_JSON` | No es necesario en localhost; se usa en producción. |

Nunca pongas valores reales en `.env.example`, el frontend o archivos versionados.

## OAuth de Google Drive

La autenticación de Drive es exclusivamente local:

1. Habilita Google Drive API en Google Cloud.
2. Configura el consentimiento OAuth.
3. Descarga credenciales de tipo Desktop y guárdalas como `credentials.json` en la raíz local.
4. Define `GOOGLE_DRIVE_FOLDER_ID` en `.env`.
5. La primera sincronización abre el navegador mediante `InstalledAppFlow`.
6. Google autoriza el alcance de lectura y la aplicación guarda `token.json` localmente.

`credentials.json` y `token.json` están excluidos por `.gitignore`. Vercel no ejecuta este flujo.

## Ejecución local

```powershell
.\.venv\Scripts\python.exe run_local.py
```

Abre <http://127.0.0.1:5000>.

La sincronización se solicita desde la interfaz o mediante `POST /api/sync`. Solo se acepta desde loopback y puede requerir la cabecera `X-Admin-Key` si `LOCAL_ADMIN_KEY` está configurada.

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Sirve `index.html`. |
| `GET` | `/assets/...` | Sirve CSS y JavaScript estáticos. |
| `GET` | `/api/health` | Informa estado, entorno y capacidades sin mostrar secretos. |
| `GET` | `/api/documents` | Devuelve nombres y URLs públicas de la biblioteca. |
| `POST` | `/api/ask` | Recibe `question` y `use_search`. |
| `POST` | `/api/sync` | Sincroniza solo en localhost. Está bloqueado en producción. |

Ejemplo de solicitud:

```json
{
  "question": "¿De qué trata el documento?",
  "use_search": true
}
```

Las preguntas deben tener entre 3 y 3000 caracteres. Las preguntas ambiguas solicitan aclaración antes de consultar documentos.

## Sincronización e indexación

La sincronización local lista los archivos compatibles de la carpeta configurada, compara sus `drive_id` y `modifiedTime` con `data/manifest.json`, y conserva los documentos sin cambios. Los nuevos o modificados se cargan al Vector Store. Las versiones antiguas se eliminan después de indexar correctamente la nueva versión. Los archivos que ya no están en Drive se retiran del Vector Store y del manifiesto.

La sincronización puede consumir recursos de Google y OpenAI. No se ejecuta desde Vercel y no debe exponerse públicamente.

En una consulta RAG, el agente recupera fragmentos del Vector Store, verifica que correspondan al referente preguntado y genera una respuesta estructurada. Solo los fragmentos utilizados y relacionados con registros válidos producen fuentes verificables.

## Pruebas automatizadas

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Las pruebas usan mocks y no requieren consultas reales a OpenAI, sincronización de Drive ni modificaciones del Vector Store.

## Despliegue en Vercel

Vercel detecta la aplicación FastAPI mediante la aplicación ASGI exportada por `app/main.py` y las dependencias de `requirements.txt`. No se requiere `vercel.json` para esta configuración básica.

El frontend se sirve desde la misma aplicación: `/` devuelve `index.html` y `/assets` sirve los recursos estáticos. Las llamadas JavaScript usan rutas relativas del mismo dominio.

### Variables de producción

Configura estas variables como privadas en Vercel:

| Variable | Configuración recomendada |
|---|---|
| `APP_ENV` | `production` |
| `OPENAI_API_KEY` | Clave privada del backend |
| `OPENAI_MODEL` | Modelo aprobado para la aplicación |
| `VECTOR_STORE_ID` | Vector Store ya sincronizado |
| `DOCUMENT_INVENTORY_JSON` | Inventario de producción con `openai_file_id`, `name` y `url` |
| `OPENAI_TIMEOUT_SECONDS` | Por ejemplo, `30` |
| `PUBLIC_ASK_ENABLED` | `false` hasta configurar protecciones contra abuso |

En Vercel no son necesarios `GOOGLE_DRIVE_FOLDER_ID`, `credentials.json`, `token.json` ni `SYNC_ENABLED`. `/api/sync` permanece deshabilitado.

`DOCUMENT_INVENTORY_JSON` no se publica en GitHub. Debe contener únicamente los registros necesarios para resolver fuentes y mostrar la biblioteca. `/api/documents` no expone `openai_file_id` al navegador.

### Diferencias entre entornos

| Capacidad | Localhost | Vercel |
|---|---|---|
| Entorno | `APP_ENV=local` | `APP_ENV=production` |
| Google Drive OAuth | Disponible | No se ejecuta |
| Sincronización | Disponible desde loopback | Bloqueada |
| Inventario | `data/manifest.json` | `DOCUMENT_INVENTORY_JSON` |
| Vector Store | Configurado localmente | `VECTOR_STORE_ID` privado |
| Consultas RAG | Disponibles localmente | Controladas por `PUBLIC_ASK_ENABLED` |
| Frontend y biblioteca | Disponibles | Disponibles |

### Actualizar documentos en producción

1. Ejecuta la sincronización desde localhost.
2. Comprueba que el manifiesto y el Vector Store contienen los documentos esperados.
3. Genera un nuevo inventario con `openai_file_id`, `name` y `url`.
4. Actualiza `DOCUMENT_INVENTORY_JSON` en Vercel sin guardarlo en Git.
5. Verifica `/api/documents` y las fuentes antes de habilitar consultas públicas.

La actualización del Vector Store y la actualización del inventario de producción son operaciones separadas.

## Seguridad, costos y mantenimiento

- `.env`, credenciales OAuth, tokens, manifiesto y respaldos están excluidos por `.gitignore`.
- Las claves solo se leen en el backend y nunca se envían al frontend.
- `PUBLIC_ASK_ENABLED=false` es el valor seguro inicial en producción.
- Antes de habilitar consultas públicas, configura rate limiting de Vercel WAF para `POST /api/ask`.
- Configura límites de gasto y alertas en el proyecto de OpenAI.
- Conserva límites de pregunta y timeout para reducir abusos y solicitudes indefinidas.
- No uses contadores en memoria como único rate limiter en un entorno serverless.
- Mantén la sincronización fuera de Vercel.
- Revisa periódicamente que el inventario coincida con el Vector Store.
- Los enlaces de PDF dependen de los permisos públicos de Google Drive.
- La duración máxima de la Function de Vercel es independiente del timeout de OpenAI y debe ajustarse según el plan contratado.

## Limitaciones actuales

- La persistencia del inventario de producción depende de la variable configurada en Vercel.
- Cambiar documentos requiere sincronizar localmente y actualizar manualmente el inventario de producción.
- La aplicación no implementa cuentas de usuario para visitantes.
- El rate limiting persistente debe configurarse en Vercel WAF.
- Google Drive puede impedir la vista previa incrustada; en ese caso se usa el enlace original.
- La eliminación de archivos del Vector Store puede tener consistencia eventual.
- Las respuestas RAG deben revisarse junto con sus fuentes documentales.

## Referencias operativas

- Producción: <https://agente-documental-tic-one.vercel.app/>
- Desarrollo local: <http://127.0.0.1:5000>
- Rama de preparación: `main`
- Rama estable local: `feature/agente-documental`
