import csv,io
from pathlib import Path
def read_upload(name,raw):
    ext=Path(name).suffix.lower()
    if ext=='.pdf':
        from pypdf import PdfReader
        return [(f'page {i+1}',p.extract_text() or '') for i,p in enumerate(PdfReader(io.BytesIO(raw)).pages[:100])]
    if ext=='.xlsx':
        from openpyxl import load_workbook
        book=load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
        return [(f'{ws.title} row {i}',' | '.join(str(v or '') for v in row)) for ws in book for i,row in enumerate(ws.values,1) if i<=500]
    if ext=='.xls':
        import xlrd
        book=xlrd.open_workbook(file_contents=raw)
        return [(f'{ws.name} row {i+1}',' | '.join(map(str,ws.row_values(i)))) for ws in book.sheets() for i in range(min(500,ws.nrows))]
    text=raw.decode('utf-8-sig')
    if ext=='.csv':return [(f'row {i}',' | '.join(row)) for i,row in enumerate(csv.reader(io.StringIO(text)),1) if i<=500]
    if ext=='.txt':return [('text',text[:40000])]
    raise ValueError('Choose CSV, Excel, PDF or text')

