# 2.3 Agente documental con Google Drive — Archivo TIC IA

Proyecto académico de **Inteligencia artificial aplicada a las TIC**, Tecnológico Nacional de México, campus Pachuca. Continuación de **2.2 Agente investigador**: se reemplaza la búsqueda pública Web Search por recuperación documental de **Google Drive**, **OpenAI Vector Stores** y **File Search (RAG)**.

## Propósito pedagógico

El alumno comprenderá que una organización necesita consultar documentos propios y autorizados, no solamente Internet. Identificará el papel de OAuth, Google Drive API, sincronización, indexación semántica, recuperación de contexto, respuestas sustentadas y trazabilidad mediante fuentes. Comparará respuestas **sin** y **con** acceso documental, observará qué sucede al modificar una fuente y realizará todas las pruebas iniciales en **localhost**. El despliegue a Vercel es un **reto autónomo**, no una configuración lista para producción.

## Arquitectura

- `app/main.py`: FastAPI, endpoints REST, frontend estático y protección local de sincronización.
- `app/core/config.py`: configuración y secretos cargados desde `.env`.
- `app/models/documento.py`: modelos de solicitud y respuesta.
- `app/services/drive_service.py`: OAuth Desktop, listado limitado a una carpeta y descarga/exportación de archivos.
- `app/services/sync_service.py`: Vector Store, manifiesto de archivos, altas, cambios y bajas.
- `app/services/agent_service.py`: Responses API + File Search y fuentes verificadas por anotaciones de archivo.
- `index.html` y `assets/`: interfaz Bootstrap 5 y clases JavaScript.
- `data/manifest.json`: estado local del índice (no se publica).

## 1. Requisitos

Python 3.11+, VS Code, Git, cuentas de Google Cloud y OpenAI API con créditos, navegador y documentos de prueba autorizados. **Las claves y los archivos de Drive no se incluyen en el ZIP.**

## 2. Configuración Google Drive

1. En [Google Cloud Console](https://console.cloud.google.com/), crea un proyecto y habilita **Google Drive API**.
2. Configura **Google Auth Platform**, pantalla de consentimiento y usuarios de prueba si corresponde.
3. Crea credenciales OAuth 2.0 de tipo **Desktop app** y descarga el archivo a la raíz del proyecto como `credentials.json`.
4. Crea una carpeta de Google Drive con **al menos cinco** documentos autorizados. Admite PDF, TXT y Google Docs nativos. Extrae el ID de su URL `/folders/ID`.
5. Este ejercicio utiliza el alcance `drive.readonly` para lectura; puede exigir validaciones adicionales al distribuir una app real. Usa una cuenta y una carpeta de laboratorio sin datos personales.

## 3. Preparar proyecto en Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edita `.env`: define `OPENAI_API_KEY`, un `OPENAI_MODEL` compatible con File Search y `GOOGLE_DRIVE_FOLDER_ID`. La plantilla `.env.example` solo contiene nombres de variables y placeholders seguros; no agregues valores reales a archivos versionados. `VECTOR_STORE_ID` se deja vacío la primera vez: el sistema lo guardará en el manifiesto. No insertes claves en el código ni en el navegador.

## 4. Ejecutar localmente

```powershell
python run_local.py
```

Abre <http://127.0.0.1:5000>. Usa **Sincronizar desde Drive** para autenticar Google, descargar/exportar los archivos autorizados e indexarlos. La primera ejecución abre el navegador OAuth en la computadora donde está corriendo Python. Después escribe preguntas sobre el contenido. Para ensayar recuperación, desactiva **File Search (RAG)** y repite exactamente la misma pregunta.

**Importante:** la sincronización usa una solicitud HTTP en localhost. Si estableces `LOCAL_ADMIN_KEY`, proporciona la cabecera `X-Admin-Key` mediante Thunder Client para `/api/sync` (el botón web no envía claves administrativas). Ejecuta el backend en `127.0.0.1`, no en `0.0.0.0`.

## 5. Endpoints

| Método | Ruta | Función |
|---|---|---|
| GET | `/api/health` | Comprueba configuración y servidor. |
| GET | `/api/documents` | Documentos ya indexados (manifiesto local). |
| POST | `/api/sync` | Indexa cambios, requiere cliente desde loopback. |
| POST | `/api/ask` | Pregunta con `question` y `use_search`. |

Ejemplo JSON para Thunder Client:

```json
{"question": "¿Qué documentos tratan sobre AWS RDS?", "use_search": true}
```

## 6. Experimentos

1. Ejecuta una pregunta muy específica presente en los archivos **sin File Search**.
2. Repite **con File Search**: inspecciona contenido y fuentes (anotaciones verificadas).
3. Prueba temas ausentes: el agente debe declarar insuficiencia de información.
4. Agrega un documento con un dato singular, sincroniza y vuelve a preguntar.
5. Modifica un documento, vuelve a sincronizar y verifica que no se duplican registros en el manifiesto.
6. Elimina un documento de prueba del Drive autorizado, sincroniza y comprueba que desaparece del manifiesto.

**Limitaciones:** las búsquedas RAG pueden generar errores; comprueba siempre las respuestas contra las fuentes. La eliminación del índice tiene **consistencia eventual** y puede tardar en reflejarse. Los resultados sin citas explícitas no se presentan como fuentes. La actualización de un mismo archivo puede crear cargos transitorios mientras se reemplaza el anterior.

## 7. Pruebas automáticas

```powershell
pytest -q
```

Las pruebas son locales y no requieren claves reales ni consumen OpenAI.

## 8. Git/GitHub y reto autónomo Vercel

```powershell
git init
git add .
git commit -m "chore: estructura inicial del agente documental"
```

Publica solamente el código; confirma `.gitignore`. **NO publiques este proyecto en Vercel sin adaptaciones de seguridad.** OAuth Desktop, `token.json`, `manifest.json`, la ausencia de sesiones de usuario y el endpoint de preguntas no son adecuados para Internet abierto. Para producción, investiga OAuth tipo **Web application**, redirecciones autorizadas, sesiones, almacenamiento persistente de tokens, control de acceso documental por usuario, protección del endpoint `/api/ask`, persistencia compartida del índice y cuotas. Los archivos locales de una función serverless pueden ser efímeros. Las variables de entorno deben configurarse en la plataforma, nunca en el frontend.

## 9. Costos y privacidad

OpenAI cobra por el uso de modelos, búsqueda y almacenamiento según su tarifario vigente. No subas a OpenAI documentos confidenciales, datos personales o material sin permiso del propietario. El material descargado se transmite a OpenAI para indexación. Revoca y rota cualquier credencial filtrada, incluso si ya fue borrada de GitHub.

## Entrega

## 10. Preparacion actual para Vercel (Camino 1)

La arquitectura prevista para Vercel es de consultas documentales. Google Drive y OAuth Desktop permanecen en localhost; Vercel no necesita `credentials.json`, `token.json` ni ejecutar `InstalledAppFlow`. La sincronizacion local actualiza el Vector Store y el manifiesto local. Despues de cambios documentales, se debe generar y configurar nuevamente el inventario de produccion.

### FastAPI y archivos estaticos

`run_local.py` importa `app` desde `app.main` y solo inicia Uvicorn dentro de `if __name__ == "__main__"`. Puede importarse como aplicacion ASGI sin arrancar un servidor manualmente. El nombre separado evita la colision entre un modulo raiz y el paquete `app/`, permitiendo que Vercel detecte `app/main.py` como aplicacion ASGI. No se requiere `vercel.json` para esta configuracion basica. Si mas adelante se necesita fijar duracion, region o exclusiones del bundle, se podra agregar explicitamente.

La ruta `/` sirve `index.html` y `/assets` sirve CSS y JavaScript mediante `StaticFiles`. El frontend usa rutas relativas como `/api/ask` y `/api/documents`, por lo que puede convivir con el backend en el mismo dominio de Vercel.

### Variables de entorno

En localhost se usan `APP_ENV=local`, `SYNC_ENABLED=true`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `GOOGLE_DRIVE_FOLDER_ID` y, opcionalmente, `VECTOR_STORE_ID`, `LOCAL_ADMIN_KEY` y `OPENAI_TIMEOUT_SECONDS`.

En Vercel se deben configurar como variables privadas:

- `APP_ENV=production`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `VECTOR_STORE_ID`
- `DOCUMENT_INVENTORY_JSON`
- `OPENAI_TIMEOUT_SECONDS=30`
- `PUBLIC_ASK_ENABLED=false` hasta configurar y probar el WAF

`GOOGLE_DRIVE_FOLDER_ID`, `credentials.json`, `token.json` y `SYNC_ENABLED` no son necesarios para el runtime publico. La sincronizacion queda bloqueada en produccion.

### Inventario de produccion

`DOCUMENT_INVENTORY_JSON` contiene unicamente `openai_file_id`, `name` y `url`. El backend valida JSON, campos obligatorios y duplicados. `/api/documents` solo devuelve `name` y `url`; los identificadores internos no se envian al frontend.

No se debe publicar el inventario real en GitHub ni incluir el `data/manifest.json` local. Si se elimina, modifica o agrega un PDF, primero se sincroniza desde localhost, se verifica el Vector Store y despues se actualiza la variable de produccion.

### Seguridad y disponibilidad

`PUBLIC_ASK_ENABLED=false` deshabilita `/api/ask` en produccion antes de inicializar el cliente OpenAI. Para habilitar consultas, primero se debe crear en Vercel una regla WAF de rate limiting para `POST /api/ask`, por IP, y establecer limites de gasto y alertas en el proyecto de OpenAI. El codigo valida preguntas de 3 a 3000 caracteres y usa un timeout de OpenAI configurable entre 1 y 120 segundos, sin reintentos automaticos.

El timeout del cliente OpenAI no sustituye el limite de duracion de Vercel. Si se necesita fijarlo, se configura desde Functions en Vercel o mediante `maxDuration` en `vercel.json`, respetando el plan contratado. No se debe habilitar la sincronizacion publica ni colocar claves en JavaScript.

### Pruebas antes de publicar

Desde la raiz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Antes de un despliegue publico se debe comprobar que localhost sigue sincronizando, que produccion carga el inventario sin leer el manifiesto local, que `/api/documents` no expone `openai_file_id`, que `/api/sync` permanece bloqueado, que `/api/ask` no realiza llamadas mientras `PUBLIC_ASK_ENABLED=false`, y que el visor conserva los enlaces publicos de Google Drive.

Repositorio GitHub con historia de commits, URL de Vercel si culminas el reto (o documentación del bloqueo), y conclusiones sobre OAuth, Google Drive API, RAG, File Search, FastAPI, OOP, Git/GitHub y seguridad.
