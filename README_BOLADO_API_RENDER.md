# BOLADO_API_RENDER

API para generar PDFs BOLADO desde JSON validado por el GPT.

## Qué hace

- Recibe un lote en formato JSON.
- Usa la plantilla oficial BOLADO.
- Usa coordenadas V3.
- Devuelve un PDF final.

## Estructura

BOLADO_API_RENDER/
├── main.py
├── requirements.txt
├── render.yaml
├── openapi_gpt_action.json
├── PLANTILLA/
│   └── PLANTILLA_BOLADO_DEFINITIVA_IMPRIMIR.pdf
├── COORDENADAS/
│   └── coordenadas_bolado_v3.json
└── EJEMPLOS/
    └── lote_validado_ejemplo.json

## Prueba local

Abrir CMD dentro de la carpeta:

```bat
py -m pip install -r requirements.txt
py -m uvicorn main:app --reload
```

Abrir en navegador:

```text
http://127.0.0.1:8000/health
http://127.0.0.1:8000/docs
```

## Subida a Render

1. Crear cuenta en GitHub.
2. Crear repositorio nuevo, por ejemplo:
   bolado-api
3. Subir todos los archivos de esta carpeta.
4. Crear cuenta en Render.
5. New → Web Service.
6. Conectar el repositorio GitHub.
7. Render detectará `render.yaml`.
8. Desplegar.

## Variables de entorno

En Render puedes usar:

```text
BOLADO_API_KEY
```

Si está definida, cada llamada debe enviar:

```text
x-api-key: TU_CLAVE
```

## Endpoint

```text
POST /generar-pdf
```

Devuelve:

```text
application/pdf
```

## Conexión con GPT

Cuando Render entregue la URL, por ejemplo:

```text
https://bolado-api.onrender.com
```

editar `openapi_gpt_action.json` y sustituir:

```text
https://TU-SERVICIO-RENDER.onrender.com
```

por la URL real.

Luego en el GPT:

Configure → Actions → Create new action → Import from schema

Pegar el contenido de `openapi_gpt_action.json`.
