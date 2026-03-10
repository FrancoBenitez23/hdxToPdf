# hdx2pdf

Convierte archivos `.hdx` de documentación Huawei a PDF.

## Instalación rápida

```bash
# 1. Clonar / descomprimir el proyecto
cd hdx2pdf

# 2. (Recomendado) Crear virtualenv
python3 -m venv venv
source venv/bin/activate          # Linux/macOS
venv\Scripts\activate             # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. En Linux, WeasyPrint necesita libs del sistema:
sudo apt install libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev

# En Windows: WeasyPrint tiene instalador GTK, ver:
# https://doc.courtbouillon.org/weasyprint/stable/first_steps.html
```

## Uso

```bash
# Archivo único → PDF en el mismo directorio
python convert.py manual.hdx

# Especificar salida
python convert.py manual.hdx -o documentacion.pdf

# Guardar en carpeta
python convert.py manual.hdx -o ./output/

# Modo verbose (ver qué hace)
python convert.py manual.hdx -v

# Sin tabla de contenidos
python convert.py manual.hdx --no-toc

# Batch: convertir toda una carpeta
python convert.py ./manuales_hdx/ -o ./pdfs/
```

## Estructura del proyecto

```
hdx2pdf/
├── convert.py          # CLI principal
├── requirements.txt
├── src/
│   ├── extractor.py    # Lee y parsea el .hdx → HDXDocument
│   └── renderer.py     # HDXDocument → PDF (WeasyPrint o reportlab)
├── output/             # PDFs generados
└── samples/            # Archivos .hdx de prueba
```

## Cómo funciona

```
archivo.hdx
    │
    ▼
HDXExtractor
  ├─ Si es ZIP  → extrae HTMLs internos
  ├─ Si es HTML → parsea directo
  └─ Fallback   → procesa como texto
    │
    ▼
HDXDocument (título + secciones)
    │
    ▼
PDFRenderer
  ├─ WeasyPrint (preferido): HTML+CSS → PDF fiel
  └─ reportlab  (fallback):  API Python → PDF
    │
    ▼
  salida.pdf
```

## Logs de procesamiento

La herramienta ahora muestra progreso en tiempo real durante la conversión.

**Salida estándar** (siempre visible):
```
[hdx2pdf] Processing: manual.hdx
[hdx2pdf] Step 1/2: Extracting content ...
  [extract] File size: 2.3 MB | Format detected: ZIP/HelpNDoc
  [extract] ZIP: 38 files total, 12 HTML files found
  [extract] manual.html → 8 section(s)
  [render] Sections to render: 42 | Engine: WeasyPrint
  [render] TOC: 42 entries
  [render] Estimated pages: 87
[hdx2pdf] Extraction done: 42 section(s) found  (0.41s)
[hdx2pdf] Step 2/2: Rendering PDF ...
[hdx2pdf] Done: manual.pdf  (1842.3 KB, 3.45s total)
```

**Con `-v` se agrega detalle fino:**
```
  [extract:v] ZIP manifest: ['index.html', 'chapter1.html', ...]
  [extract:v] Heading found (h2): "1.1 Overview"
  [render:v] HTML length: 148320 chars
  [render:v] TOC breakdown: h1=5, h2=28, h3=9
```

Los prefijos `[extract]` y `[render]` indican el módulo que genera el log.

## Troubleshooting

**"No module named weasyprint"**
→ `pip install weasyprint` o usá el fallback con reportlab (se activa automáticamente)

**El PDF sale vacío**
→ Corré con `-v` para ver qué secciones detectó el extractor.
→ El formato interno de tu `.hdx` puede ser binario/propietario — abrilo con un
  editor hex o `file archivo.hdx` para verificar el formato real.

**Caracteres raros / encoding**
→ El extractor usa `errors="replace"` por defecto. Si el documento es GB2312
  (común en docs Huawei chinos), editá `extractor.py` línea del decode:
  `raw.decode("gb2312", errors="replace")`
