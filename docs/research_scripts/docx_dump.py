import sys,zipfile,re
sys.stdout.reconfigure(encoding='utf-8')
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
import xml.etree.ElementTree as ET
def txt(e): return ''.join(t.text or '' for t in e.iter(W+'t')).strip()
for f in sys.argv[1:]:
    root=ET.fromstring(zipfile.ZipFile(f).read('word/document.xml'))
    body=root.find(W+'body')
    print('='*20,f)
    ti=0
    for el in body:
        if el.tag==W+'p':
            t=txt(el)
            if t and (len(t)<90) and (t.isupper() or re.match(r'^([IVX]+\.|[A-Z]\.|\d+\.|Annex|Table)',t)): print('P:',t)
        elif el.tag==W+'tbl':
            rows=el.findall(W+'tr'); ti+=1
            hdr=[ ' / '.join(txt(c) for c in r.findall(W+'tc'))[:200] for r in rows[:3]]
            print(f'  TABLE{ti} rows={len(rows)}'); [print('     ',h) for h in hdr]
