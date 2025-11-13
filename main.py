# main.py
import os
import json
import re
import pdfplumber
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph,
                                Spacer, PageBreak, TableOfContents, NextPageTemplate)
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus.flowables import KeepTogether

# ---------------------------
# Utils: load config
# ---------------------------
CONFIG_PATH = "config.json"

def load_config(path=CONFIG_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

cfg = load_config()

# Choose pagesize
PAGE_SIZE = A4 if cfg["layout"].get("page_size", "A4").upper() == "A4" else letter
MARGINS = cfg["layout"]["margins"]
PAGE_WIDTH, PAGE_HEIGHT = PAGE_SIZE

# ---------------------------
# PDF parsing heuristics
# ---------------------------
def extract_text_from_pdf(path):
    text_pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            t = p.extract_text()
            if t:
                text_pages.append(t)
    return "\n".join(text_pages).strip()

def split_lines(text):
    # normalize line endings and collapse multiple blank lines to single
    lines = [ln.strip() for ln in text.splitlines()]
    # drop lines that are empty except keep splits
    return [ln for ln in lines if ln != ""]

def heuristic_parse(text):
    """
    Heurística razoável para texto corrido:
    - primeira(s) linhas (até max_title_lines) como título
    - linha seguinte que contenha ';' or ',' or ' and ' ou ' e ' -> autores
    - procurar por 'Eixo' ou 'Eixo temático' ou 'Área' no texto; se encontrado, captura
    - resto -> resumo (texto)
    Devolve dicionário com campos: titulo, autores (lista), eixo, texto
    """
    lines = split_lines(text)
    max_title_lines = cfg["parser"].get("max_title_lines", 3)
    title_lines = []
    idx = 0

    # build title from first up-to-N non-empty lines but stop if a likely author line appears
    while idx < len(lines) and len(title_lines) < max_title_lines:
        candidate = lines[idx]
        # if candidate looks like 'Resumo' or 'Abstract' then stop
        if re.match(r'^(Resumo|Abstract)\b', candidate, re.IGNORECASE):
            break
        # if candidate contains patterns typical of author lines, break and treat previous ones as title
        if ((";" in candidate or "," in candidate) and len(candidate) < cfg["parser"].get("author_line_max_length",200)) or re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+', candidate):
            # if it's probably authors, stop title capture
            break
        title_lines.append(candidate)
        idx += 1

    title = " ".join(title_lines).strip() if title_lines else (lines[0] if lines else "Sem título")

    # next, try to find authors
    authors = []
    # scan next few lines for an authors line (heuristic)
    for i in range(idx, min(len(lines), idx + 4)):
        ln = lines[i]
        # patterns: semicolon-separated, comma-separated short line, or ' - ' between author and institution
        if ";" in ln or ("," in ln and len(ln) < 200) or re.search(r'\b[e|and]\b|\be\b', ln):
            # split by ; or , or ' and ' or ' e '
            parts = re.split(r';|,|\band\b|\be\b', ln)
            parts = [p.strip() for p in parts if p.strip()]
            # remove if line contains 'Resumo' or 'Eixo' etc
            if parts:
                authors = parts
                idx = i + 1
                break
        # detect lines that are likely affiliations like 'Universidade...' -> skip as authors
        if re.search(r'(Universidade|Instituto|Departamento|Institu|Centro|Faculdade)', ln, re.IGNORECASE):
            continue
    if not authors:
        # fallback: try to detect a short line after title as author
        if idx < len(lines) and len(lines[idx]) < 120:
            maybe = lines[idx]
            if re.search(r'\w', maybe) and not re.search(r'(Resumo|Abstract|Eixo|Palavras)', maybe, re.IGNORECASE):
                authors = [a.strip() for a in re.split(r';|,|\band\b|\be\b', maybe) if a.strip()]
                idx += 1

    # find eixo (search whole text for keywords)
    eixo = None
    m = re.search(r'(Eixo temático|Eixo|Área temática|Área):?\s*(.+)', text, re.IGNORECASE)
    if m:
        eixo = m.group(2).split("\n")[0].strip()
    else:
        # try capture lines that look like section labels
        for ln in lines[:8]:
            if re.search(r'(Eixo|Área|Tema)', ln, re.IGNORECASE):
                # maybe the line itself is the axis
                eixo = ln.strip()
                break

    # The rest of the text (after idx) is considered the resumo
    resumo_lines = lines[idx:]
    # remove leading headers like 'Resumo:' or 'Abstract:'
    if resumo_lines and re.match(r'^(Resumo|Abstract)\b', resumo_lines[0], re.IGNORECASE):
        resumo_lines = resumo_lines[1:]

    texto = "\n\n".join(resumo_lines).strip()
    if not texto:
        texto = text  # fallback: entire text

    return {
        "titulo": title,
        "autores": authors if authors else ["Autor desconhecido"],
        "eixo": eixo if eixo else "Comunicações",
        "texto": texto
    }

# ---------------------------
# Document generation (ReportLab)
# ---------------------------

# styles
styles = getSampleStyleSheet()
style_title = ParagraphStyle('TitleGEL', parent=styles['Heading1'], fontName=cfg["layout"]["font"]["bold"],
                             fontSize=18, alignment=TA_CENTER, spaceAfter=8)
style_section = ParagraphStyle('Section', parent=styles['Heading2'], fontName=cfg["layout"]["font"]["bold"],
                               fontSize=14, alignment=TA_LEFT, spaceBefore=12, spaceAfter=6)
style_authors = ParagraphStyle('Authors', parent=styles['Normal'], fontName=cfg["layout"]["font"]["italic"],
                               fontSize=10, alignment=TA_CENTER, spaceAfter=6)
style_text = ParagraphStyle('BodyText', parent=styles['Normal'], fontName=cfg["layout"]["font"]["base"],
                            fontSize=11, leading=14, alignment=TA_JUSTIFY, spaceAfter=8)
style_toc_heading = ParagraphStyle('TOCHeading', parent=styles['Heading1'], fontName=cfg["layout"]["font"]["bold"],
                                   fontSize=16, alignment=TA_LEFT, spaceAfter=12)

# header/footer callback
def header_footer(canvas, doc):
    canvas.saveState()
    # footer: page number centered
    page_num = canvas.getPageNumber()
    footer_text = f"{page_num}"
    canvas.setFont(cfg["layout"]["font"]["base"], 9)
    canvas.drawCentredString(PAGE_WIDTH / 2.0, 15, footer_text)
    canvas.restoreState()

def build_caderno(resumos_list, output_path="saida/caderno_final.pdf"):
    # order by eixo -> group
    from collections import defaultdict, OrderedDict
    grouped = defaultdict(list)
    for r in resumos_list:
        grouped[r['eixo']].append(r)

    # create document
    doc = BaseDocTemplate(output_path, pagesize=PAGE_SIZE,
                          leftMargin=MARGINS['left'], rightMargin=MARGINS['right'],
                          topMargin=MARGINS['top'], bottomMargin=MARGINS['bottom'])

    frame = Frame(MARGINS['left'], MARGINS['bottom'],
                  PAGE_WIDTH - MARGINS['left'] - MARGINS['right'],
                  PAGE_HEIGHT - MARGINS['top'] - MARGINS['bottom'], id='normal')

    template = PageTemplate(id='Content', frames=frame, onPage=header_footer)
    doc.addPageTemplates([template])

    story = []

    # ---- Cover page (built from config)
    evento = cfg['evento']
    story.append(Spacer(1, PAGE_HEIGHT * 0.25))
    story.append(Paragraph(evento.get('nome', ''), ParagraphStyle('cover_title', fontName=cfg["layout"]["font"]["bold"], fontSize=28, alignment=TA_CENTER, spaceAfter=14)))
    story.append(Paragraph(cfg["layout"].get("titulo_caderno", "Caderno de Resumos"), ParagraphStyle('cover_sub', fontName=cfg["layout"]["font"]["base"], fontSize=20, alignment=TA_CENTER, spaceAfter=12)))
    story.append(Spacer(1, 12))
    story.append(Paragraph(evento.get('instituicao', ''), ParagraphStyle('cover_inst', fontName=cfg["layout"]["font"]["base"], fontSize=12, alignment=TA_CENTER, spaceAfter=8)))
    story.append(Paragraph(evento.get('organizadores', ''), ParagraphStyle('cover_org', fontName=cfg["layout"]["font"]["italic"], fontSize=10, alignment=TA_CENTER, spaceAfter=6)))
    story.append(Spacer(1, PAGE_HEIGHT * 0.18))
    story.append(Paragraph(evento.get('local', ''), ParagraphStyle('cover_loc', fontName=cfg["layout"]["font"]["base"], fontSize=10, alignment=TA_CENTER)))
    story.append(Paragraph(evento.get('data', ''), ParagraphStyle('cover_date', fontName=cfg["layout"]["font"]["base"], fontSize=10, alignment=TA_CENTER)))
    story.append(PageBreak())

    # ---- Table of Contents
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(fontName=cfg["layout"]["font"]["base"], fontSize=12, leftIndent=20, firstLineIndent=-20, spaceBefore=6),
        ParagraphStyle(fontName=cfg["layout"]["font"]["base"], fontSize=10, leftIndent=40, firstLineIndent=-20, spaceBefore=3)
    ]
    story.append(Paragraph("Sumário", style_toc_heading))
    story.append(toc)
    story.append(PageBreak())

    # ---- content: for each eixo create a section and add entries
    # Keep visual order deterministic
    for eixo in sorted(grouped.keys()):
        # add section heading with TOC entry (level 0)
        sect_title = Paragraph(eixo, style_section)
        story.append(KeepTogether([sect_title]))
        # register in toc: addEntry(level, text, pageNumber) will be done automatically if we use Paragraph and add 'toc' attributes
        # Trick: set attribute for automatic TOC capture
        sect_title._bookmarkName = eixo
        doc.notify('TOCEntry', (0, eixo, doc.page))
        story.append(Spacer(1, 6))

        for r in grouped[eixo]:
            # title (register as level 1 in TOC)
            p_title = Paragraph(r['titulo'], ParagraphStyle('item_title', parent=styles['Heading3'], fontName=cfg["layout"]["font"]["bold"], fontSize=12, alignment=TA_LEFT, spaceAfter=4))
            # set TOC info:
            doc.notify('TOCEntry', (1, r['titulo'], doc.page))
            story.append(p_title)
            # authors centered italic
            story.append(Paragraph(", ".join(r['autores']), style_authors))
            # text
            # break summary into paragraphs at blank lines
            paras = [p.strip() for p in re.split(r'\n\s*\n', r['texto']) if p.strip()]
            for p in paras:
                story.append(Paragraph(p.replace('\n',' '), style_text))
            story.append(Spacer(1, 12))
        story.append(PageBreak())

    # build
    doc.build(story)
    print(f"Caderno gerado em: {output_path}")

# ---------------------------
# Main: walk folder, parse PDFs and generate
# ---------------------------
def main():
    folder = os.path.join("dados", "resumos")
    if not os.path.isdir(folder):
        print("Crie a pasta dados/resumos e coloque seus PDFs lá.")
        return

    pdf_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("Nenhum PDF encontrado em dados/resumos.")
        return

    parsed = []
    for p in sorted(pdf_files):
        print("Processando:", p)
        raw = extract_text_from_pdf(p)
        meta = heuristic_parse(raw)
        # we add filename in case you want to track
        meta['source'] = os.path.basename(p)
        parsed.append(meta)

    os.makedirs("saida", exist_ok=True)
    build_caderno(parsed, output_path=os.path.join("saida", "caderno_final.pdf"))

if __name__ == "__main__":
    main()
