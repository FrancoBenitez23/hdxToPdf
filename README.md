# hdx2pdf

Convierte archivos `.hdx` de documentación Huawei a PDF.

> **Estado:** prototipo v1 funcional. Probado con archivos de hasta 171 MB y 17.000+ secciones.

## Instalación

```bash
python3 -m venv env
source env/bin/activate
pip install -r requirements.txt
```

En Linux, WeasyPrint requiere libs del sistema:
```bash
sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev
```

## Uso

```bash
# Básico
python convert.py manual.hdx

# Especificar salida
python convert.py manual.hdx -o documentacion.pdf

# Guardar en carpeta
python convert.py manual.hdx -o ./output/

# Verbose (muestra detalle del proceso)
python convert.py manual.hdx -v

# Sin tabla de contenidos
python convert.py manual.hdx --no-toc

# Batch: convertir toda una carpeta
python convert.py ./manuales_hdx/ -o ./pdfs/
```

## Cómo funciona

```
archivo.hdx
    │
    ▼
HDXExtractor
  ├─ ZIP  → extrae HTMLs internos
  ├─ HTML → parsea directo
  └─ Texto → divide por encabezados numerados
    │
    ▼
HDXDocument (título + secciones)
    │
    ▼
PDFRenderer
  ├─ WeasyPrint (principal): HTML+CSS → PDF con estilo Huawei
  └─ reportlab  (fallback):  sin dependencias GTK
    │
    ▼
  salida.pdf
```

## Documentos grandes

Para archivos con más de 200 secciones, el renderer divide el documento en chunks de 200 secciones y los renderiza en paralelo (6 workers), luego los une con pikepdf. Esto permite convertir documentos de miles de secciones sin colgar.

```
[render] Large document (17462 sections) — splitting into 88 chunk(s)
[render] Rendering 88 chunk(s) in parallel (max_workers=6) ...
[render]   Chunk 3/88 done ...
[render]   Chunk 1/88 done ...
[render] Merging 88 chunk PDF(s) -> output.pdf ...
```

El orden de los logs no es secuencial (es paralelo), pero el PDF final siempre respeta el orden correcto.

## Estructura

```
hdx2pdf/
├── convert.py       # CLI: argumentos, modo batch, orquestación
├── extractor.py     # Lee el .hdx → HDXDocument con secciones
├── renderer.py      # HDXDocument → PDF (WeasyPrint + pikepdf)
└── requirements.txt
```

## Troubleshooting

**PDF vacío**
→ Corré con `-v` para ver cuántas secciones detectó el extractor.

**Caracteres raros / encoding**
→ Para documentos Huawei en chino (GB2312), cambiá en `extractor.py`:
`raw.decode("gb2312", errors="replace")`
