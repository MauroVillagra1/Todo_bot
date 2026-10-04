# Cómo se detectan y guardan las actualizaciones

Este documento explica cómo el sistema se entera de que una fuente publicó o cambió algo, y cómo lo guarda **sin usar IA y sin gastar tokens**.

---

## La idea en una frase

Dos veces por día, un proceso automático (el **worker**) le pregunta a cada fuente activa *"¿qué cambió desde la última vez?"*. Guarda solo lo nuevo y nunca borra lo anterior.

```
GitHub Actions (cada 6 horas: 00, 06, 12 y 18)
        │
        ▼
scripts/run_ingest.py ──► para cada fuente activa:
        │                   1. ¿Qué cambió desde la última revisión?
        │                   2. ¿Ya tengo exactamente este contenido?  → descartar
        │                   3. Si es nuevo o cambió                   → guardar versión
        │                   4. Anotar qué pasó (ingestas + métricas)
        ▼
PostgreSQL (Neon)
```

---

## Paso a paso

### 1. Preguntar solo por lo que cambió

Cada fuente guarda en `fuentes.ultima_revision` la fecha de la última modificación que vio.

Para **Sistemas FRT** (un WordPress), el worker pide a la API pública:

```
https://sistemasfrtutn.ar/wp-json/wp/v2/posts?modified_after=<ultima_revision>
```

WordPress devuelve **solo** los posts creados o editados después de esa fecha. Si no cambió nada, devuelve una lista vacía y el worker termina sin procesar nada.

- La fecha que se guarda es **la de la fuente**, no la del reloj de la PC. Así un reloj desfasado no puede hacer que se salteen cambios. Pasa en la práctica: tu PC adelanta unos 4 minutos respecto de Neon.
- Se pide con un **margen de 5 minutos** hacia atrás, por si algo se publicó justo durante la corrida anterior. Lo que llegue repetido se descarta en el paso siguiente.

### 2. Descartar repetidos con un hash

Cada contenido se convierte en texto plano y se calcula su **hash sha256**, una "huella digital" del texto.

- Antes de calcularlo se ignoran los espacios y las mayúsculas, así que un cambio solo de formato **no** cuenta como versión nueva.
- Si ya existe una publicación con el mismo ID y el mismo hash → es un **duplicado**: se descarta y se suma a la métrica `duplicados_descartados`.

### 3. Guardar la versión nueva, sin borrar la anterior

| Caso | Qué pasa |
|---|---|
| Post que nunca vimos | Se crea en `publicaciones` con `vigente = true` |
| Post que ya teníamos, con texto distinto | La versión anterior queda con `vigente = false` y se crea una fila nueva con `vigente = true` |
| Post igual al que ya teníamos | No se guarda nada (duplicado) |

Además de la publicación se guarda:
- `contenido_original`: el HTML tal cual vino de la fuente.
- `fecha_publicacion`, `fecha_modificacion` (de la fuente) y `fecha_captura` (cuándo lo bajamos).
- Los **chunks**: el texto partido en fragmentos de unos 1200 caracteres, cada uno con el título adelante. Postgres les calcula solo el índice de búsqueda en español (`chunks.tsv`).

### 4. Registrar qué pasó

Cada corrida crea una fila en `ingestas`:

| Campo | Significado |
|---|---|
| `estado` | `OK`, `ERROR` (la fuente no respondió) o `EN_CURSO` |
| `nuevos` | publicaciones nuevas o versiones nuevas |
| `duplicados` | repetidos descartados por hash |
| `errores` / `detalle_errores` | qué falló y en qué ítem |

Y suma contadores del día en `metricas_diarias`: `documentos_procesados`, `documentos_actualizados`, `duplicados_descartados` y `errores_ingesta`.

### Si algo falla

- Si **un ítem** falla, se anota el error y se sigue con el resto.
- Si **la fuente se cae** a mitad de camino, lo ya procesado queda guardado.
- En los dos casos `ultima_revision` **no avanza**. La corrida siguiente vuelve a pedir desde la misma fecha, y lo que ya estaba guardado se descarta por hash sin costo.

---

## Ejemplos

**Nadie publicó nada:** WordPress devuelve una lista vacía → `nuevos=0` y la corrida termina en segundos.

**El departamento publica "Mesas de examen de diciembre":** llega en la próxima corrida → `nuevos=1`. Queda guardado con sus chunks y ya se puede buscar.

**Al otro día corrigen la fecha de una mesa en ese mismo post:** WordPress actualiza `modified` → el worker lo trae, el hash es distinto → la versión vieja queda `vigente=false` y se crea la nueva. Las dos versiones quedan guardadas.

**El sitio está caído:** la ingesta queda en `ERROR` con el detalle, GitHub Actions marca la corrida en rojo, y la corrida siguiente lo reintenta desde la misma fecha.

---

## Dónde ver las actualizaciones

### En GitHub
**Actions → Ingesta**. Cada corrida muestra un resumen como este:
```
[OK] Sistemas FRT: nuevos=2 duplicados=0 errores=0
```

### En la consola SQL de Neon

```sql
-- Últimas corridas
SELECT f.nombre, i.estado, i.inicio, i.nuevos, i.duplicados, i.errores
FROM ingestas i JOIN fuentes f ON f.id = i.fuente_id
ORDER BY i.inicio DESC LIMIT 10;

-- Lo último que cambió en las fuentes
SELECT titulo, url, fecha_modificacion, fecha_captura
FROM publicaciones WHERE vigente
ORDER BY fecha_modificacion DESC LIMIT 20;

-- Historial de versiones de una publicación
SELECT id, vigente, fecha_modificacion, fecha_captura, left(hash, 8) AS hash
FROM publicaciones WHERE id_externo = 'posts:19756' ORDER BY id;

-- Métricas de los últimos 7 días
SELECT * FROM metricas_diarias
WHERE dia > current_date - 7 ORDER BY dia DESC, metrica;
```

El panel de administración (etapa 8) va a mostrar lo mismo sin necesidad de SQL.

---

## Cómo correrlo a mano

**Desde tu PC** (usa el `DATABASE_URL` de `backend/.env`):
```bash
cd backend
python scripts/run_ingest.py                       # todas las fuentes activas
python scripts/run_ingest.py --fuente "Sistemas FRT"
```

**Desde GitHub:** Actions → Ingesta → **Run workflow**. Opcionalmente indicás el nombre de una fuente.

### Configuración necesaria en GitHub (una sola vez)

En el repo: **Settings → Secrets and variables → Actions → New repository secret**
- Nombre: `DATABASE_URL`
- Valor: el mismo `DATABASE_URL` de `backend/.env`.

Sin ese secret, el workflow falla.

---

## PDFs de Sistemas FRT (horarios, calendarios, resoluciones)

La fuente **Sistemas FRT (PDFs)** lee la biblioteca de medios de WordPress:
```
https://sistemasfrtutn.ar/wp-json/wp/v2/media?mime_type=application/pdf&modified_after=<ultima_revision>
```
- Usa el mismo mecanismo que los posts: solo pide lo nuevo, descarga el PDF y extrae el texto con `pypdf`, todo en local y sin costo.
- Hace **un chunk por página**. En los horarios cada página es una comisión, así que una pregunta como "¿horario de 3K01?" encuentra la página justa.
- **Se excluyen los CVs de docentes** (`CV_…`, `…-CV-…`, `Curriculum…`): son datos personales y no le sirven al chat. El patrón está en `fuentes.config.excluir_pdf`.
- Si un PDF se vuelve a subir con el mismo contenido, se descarta por hash. Si cambia, se guarda una versión nueva.
- El original se guarda comprimido si pesa hasta 1 MB. Si es más grande, queda la URL de la fuente.
- Limitación: los PDFs **escaneados** (imágenes) no tienen texto, y leerlos requeriría OCR.

## Instagram y canales de WhatsApp (autorizados)

| Fuente | Cómo entra el contenido |
|---|---|
| **WhatsApp** | No existe una API para leer canales. Un **MOD** carga el posteo desde el **Panel → Cargar publicación**: link, título, texto y fecha. |
| **Instagram** | Automático con **Instaloader desde la PC local** al iniciar Windows (ver abajo). También carga manual, o la API oficial de Meta si el dueño de la cuenta genera un token. |

Lo cargado a mano pasa por el **mismo circuito** que lo automático: hash, versionado si se vuelve a cargar el mismo link con otro texto, chunks y verificación. El estado depende de la confiabilidad de la fuente: 100% → CONFIRMADA, 90% → PROBABLE, 50% → NO_CONFIRMADA.

### WhatsApp por reenvío al número del bot (API oficial, costo 0)

Leer canales automáticamente desde un WhatsApp personal solo se puede con herramientas no oficiales, que violan los términos de Meta y arriesgan el número. La forma permitida:

1. El bot tiene su propio número: el **número de prueba gratuito** que da Meta al crear la app. No necesita chip.
2. Cuando un canal publica, **reenviás el posteo** desde tu WhatsApp al contacto del bot (un toque).
3. Meta llama a `POST /api/v1/webhooks/whatsapp`. Se verifica la firma, se aceptan **solo números autorizados** y el texto (o el pie de la foto) entra como NO CONFIRMADA.
4. Si el mismo posteo se reenvía dos veces, se descarta por su texto.

Configuración (una vez):
- Meta Business + app en developers.facebook.com con el producto **WhatsApp**.
- Variables en Vercel (`back-bot`): `WHATSAPP_APP_SECRET` (Configuración → Básica → Clave secreta), `WHATSAPP_VERIFY_TOKEN` (palabra inventada) y `WHATSAPP_REENVIADORES` (tu número, solo dígitos, ej. `["5493815551111"]`).
- En la app de Meta → WhatsApp → Configuración → Webhook: URL `https://back-bot-6icc.vercel.app/api/v1/webhooks/whatsapp`, el mismo verify token, y suscribirse a **messages**.
- Con el número de prueba hay que agregar tu número como destinatario permitido en la app.

### Instagram con Instaloader (PC local, al iniciar Windows)

Las 4 cuentas de Instagram (`config: {"instaloader": true}`) se leen desde la PC, no desde GitHub Actions: Instagram bloquea las IPs de datacenter y pide login. Se lee el texto del posteo (caption), solo lo publicado después de la última revisión. La primera vez se leen los últimos 30 posts.

Configuración (una vez, en PowerShell desde la raíz del repo):
```powershell
pip install instaloader
instaloader --login TU_USUARIO      # pide la contraseña; conviene una cuenta secundaria
.\scripts\instalar_instagram_local.ps1 -Usuario TU_USUARIO
```
- Queda un acceso directo `UTNIA Instagram` en la carpeta Inicio (`shell:startup`). Al iniciar sesión corre oculto `scripts/instagram_local.ps1`.
- Registro de cada corrida: `%LOCALAPPDATA%\UTNIA\instagram.log`.
- Para correrlo a mano: `.\scripts\instagram_local.ps1`.
- Si Instagram cierra la sesión, se vuelve a ejecutar `instaloader --login TU_USUARIO`.
- Scrapear va contra los términos de Instagram: el riesgo es para la cuenta usada, por eso conviene que sea secundaria.

### Activar Instagram por API oficial (opcional, costo 0)

1. El dueño de la cuenta (que debe ser **profesional**, Business o Creator) autoriza una app de Meta y genera un **token de larga duración**.
2. El token se guarda como **secret** de GitHub, por ejemplo `IG_TOKEN_SAE_FRT`, y se agrega al `env:` del workflow `ingest.yml`.
3. En la fuente se indica el nombre de esa variable:
   ```sql
   UPDATE fuentes SET config = '{"token_env": "IG_TOKEN_SAE_FRT"}' WHERE nombre = 'SAE FRT (Instagram)';
   ```
- El token **dura unos 60 días** y hay que renovarlo.
- Se lee el texto del posteo (caption). El texto que está **dentro de las imágenes** (flyers) no se lee.

## Activar o desactivar fuentes

Por ahora se hace por SQL; el panel de la etapa 8 lo va a permitir desde la web:
```sql
UPDATE fuentes SET activa = false WHERE nombre = 'Sistemas FRT';
```
Una fuente inactiva no se consulta, así que no tiene ningún costo.

---

## Limitaciones conocidas

- **Borrados:** si la fuente **elimina** un post, `modified_after` no lo informa, y el post queda guardado como vigente. Más adelante se puede sumar una revisión periódica que compare la lista completa de IDs.
- **Eventos de Sistemas FRT** (`tp_event`): no están expuestos en la API pública, así que por ahora no se leen.
- **UTN FRT (`frt.utn.edu.ar`):** el sitio está caído, así que su adaptador web se construye cuando vuelva (etapa 4).
- **Primera carga:** baja todo el historial (~589 publicaciones y ~120 PDFs) y tarda bastante. Las corridas siguientes solo traen lo modificado.
- **Clasificación y verificación** (estados CONFIRMADA, PROBABLE, etc.): llegan en la etapa 5. Por ahora solo se guarda el contenido.
