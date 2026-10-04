# Guía de prueba del backend

## 1. Requisitos previos

- Docker y Docker Compose instalados
- Python 3.12 instalado

---

## 2. Configurar el entorno

```bash
# Desde la raíz del proyecto
cd "/home/kali/Escritorio/Proyecto BOT/backend"
cp .env.example .env
```

Editá el `.env` y completá estos campos mínimos:

```env
DATABASE_URL=postgresql://uni_user:uni_pass@localhost:5432/asistente_uni
SECRET_KEY=clave_secreta_para_pruebas_locales_123456
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ANTHROPIC_API_KEY=placeholder
VOYAGE_API_KEY=placeholder
ENVIRONMENT=development
CORS_ORIGINS=http://localhost:5173
```

---

## 3. Levantar la base de datos

```bash
cd "/home/kali/Escritorio/Proyecto BOT"
docker compose up db -d
```

Verificar que esté corriendo:
```bash
docker compose ps
```

---

## 4. Instalar dependencias Python

```bash
cd "/home/kali/Escritorio/Proyecto BOT/backend"
pip install -r requirements.txt
```

---

## 5. Crear las tablas (migraciones)

```bash
cd "/home/kali/Escritorio/Proyecto BOT/backend"

# Generar la migración inicial a partir de los modelos
alembic revision --autogenerate -m "initial"

# Aplicarla a la base de datos
alembic upgrade head
```

Si todo salió bien vas a ver algo como:
```
INFO  [alembic.runtime.migration] Running upgrade -> xxxx, initial
```

---

## 6. Cargar datos de prueba

```bash
cd "/home/kali/Escritorio/Proyecto BOT/backend"
python seed.py
```

Salida esperada:
```
── Usuarios ──────────────────────────
  ✓ creado: administrador — admin@universidad.edu / Admin1234
  ✓ creado: profesor_directivo — garcia@universidad.edu / Profe1234
  ✓ creado: alumno — ana@universidad.edu / Alumno1234
  ✓ creado: alumno — carlos@universidad.edu / Alumno1234
...
✅ Seed completado exitosamente.
```

---

## 7. Levantar el servidor

```bash
cd "/home/kali/Escritorio/Proyecto BOT/backend"
uvicorn app.main:app --reload
```

---

## 8. Probar con Swagger UI

Abrí en el navegador:
```
http://localhost:8000/docs
```

### Flujo básico de prueba:

**a) Health check** → `GET /health`
Debería devolver `{"status": "ok"}`

**b) Login como administrador**
- Endpoint: `POST /api/v1/auth/login`
- Body:
```json
{
  "email": "admin@universidad.edu",
  "password": "Admin1234"
}
```
- Copiá el `access_token` de la respuesta

**c) Autenticarse en Swagger**
- Hacé clic en el botón **Authorize** (candado arriba a la derecha)
- Pegá el token en el campo `bearerAuth`

**d) Ver tus datos**
- `GET /api/v1/auth/me` → devuelve el usuario logueado

**e) Probar el chat**
- `POST /api/v1/chat/`
```json
{
  "mensaje": "¿Cuándo son las mesas de examen?"
}
```
- Mientras no haya información institucional cargada responde "Todavía no tengo información institucional cargada…" sin llamar a la IA.
- Más de `CHAT_MAX_POR_MINUTO` mensajes en un minuto → `429`.

---

## 9. Probar con curl (alternativa a Swagger)

```bash
# Login
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@universidad.edu","password":"Admin1234"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtenido: ${TOKEN:0:20}..."

# Consultar el chat
curl -s -X POST http://localhost:8000/api/v1/chat/ \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"mensaje":"¿Cuándo son las mesas de examen?"}' | python3 -m json.tool
```

---

## Usuarios disponibles en el seed

| Email | Contraseña | Rol |
|---|---|---|
| admin@universidad.edu | Admin1234 | administrador |
| garcia@universidad.edu | Profe1234 | profesor_directivo |
| ana@universidad.edu | Alumno1234 | alumno (Comisión 2K1) |
| carlos@universidad.edu | Alumno1234 | alumno (Comisión 3N2) |
