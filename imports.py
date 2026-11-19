"""Parse authorised internal evidence and chunk it without silently discarding pages."""
import csv
import io
from pathlib import Path


def read_upload(name, raw):
    ext=Path(name).suffix.lower()
    if ext=='.pdf':
        from pypdf import PdfReader
        pdf=PdfReader(io.BytesIO(raw))
        if len(pdf.pages)>150:
            raise ValueError('Please split PDFs longer than 150 pages')
        return [(f'page {i+1}',p.extract_text() or '') for i,p in enumerate(pdf.pages)]
    if ext=='.xlsx':
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        try:
            return [(f'{ws.title} row {i}',' | '.join('' if v is None else str(v) for v in row))
                    for ws in book for i,row in enumerate(ws.values,1) if i<=1000]
        finally:
            book.close()
    if ext=='.xls':
        import xlrd
        book=xlrd.open_workbook(file_contents=raw)
        return [(f'{ws.name} row {i+1}',' | '.join(map(str,ws.row_values(i))))
                for ws in book.sheets() for i in range(min(1000,ws.nrows))]
    text=raw.decode('utf-8-sig')
    if ext=='.csv':
        return [(f'row {i}',' | '.join(row)) for i,row in enumerate(csv.reader(io.StringIO(text)),1) if i<=1000]
    if ext=='.txt':
        return [('text',text)]
    raise ValueError('Choose CSV, Excel, PDF or text')


def chunks(rows, max_chars=4400, max_chunks=120):
    """Retain record locations for inline evidence, with explicit overflow error."""
    pieces=[]
    for location,value in rows:
        value=' '.join(str(value).split())
        if not value:
            continue
        label=str(location)[:120]
        max_body=max_chars-len(label)-5
        for offset in range(0,len(value),max_body):
            pieces.append(f'[{label} characters {offset+1}–{min(offset+max_body,len(value))}] {value[offset:offset+max_body]}')
    out=[]
    current=''
    for piece in pieces:
        if len(current)+len(piece)+1>max_chars and current:
            out.append(current)
            current=''
        current=(current+'\n'+piece).strip()
    if current:
        out.append(current)
    if len(out)>max_chunks:
        raise ValueError(f'This input creates {len(out)} chunks; please split it into smaller files (limit {max_chunks} chunks per upload)')
    return out
