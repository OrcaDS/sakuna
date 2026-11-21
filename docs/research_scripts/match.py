import sys,json,re,zipfile,unicodedata,xml.etree.ElementTree as ET
sys.stdout.reconfigure(encoding='utf-8')
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def txt(e): return ''.join(t.text or '' for t in e.iter(W+'t')).strip()
ABBR=[(r'\bsta\.?\s',' santa '),(r'\bsto\.?\s',' santo '),(r'\bgen\.?\s',' general '),(r'\bpres\.?\s',' president '),(r'\bmun\.?\s',' ')]
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()
    s=re.sub(r'\(.*?\)','',s)
    for a,b in ABBR: s=re.sub(a,b,s+' ')
    s=re.sub(r'\bcity of\b|\bcity\b|\bmunicipality of\b|\bregion\b','',s)
    return re.sub(r'[^a-z0-9]','',s)
L=lambda f: json.load(open(f,encoding='utf-8'))
R,P,M=L('psgc_regions.json'),L('psgc_provinces.json'),L('psgc_cities-municipalities.json')
reg={}
for r in R:
    for k in (r['name'],r['regionName']): reg[norm(k)]=r['code']
for k,v in {'ncr':'130000000','car':'140000000','armm':'190000000','barmm':'190000000','caraga':'160000000','mimaropa':'170000000','iva':'040000000','ivb':'170000000','nir':'180000000'}.items(): reg.setdefault(k,v)
for r in R:  # roman numerals
    m=re.match(r'Region ([IVX]+)(-A|-B)?$',r['regionName'])
    if m: reg[norm(m[1]+(m[2] or ''))]=r['code']
prov={}
for p in P: prov.setdefault(norm(p['name']),[]).append(p)
towns={}
for t in M:
    for k in {norm(t['name']),norm(t['oldName'] or '')}-{''}: towns.setdefault(k,[]).append(t)
def find_town(name,pc,rc):
    c=towns.get(norm(name),[])
    for f in (lambda t:t['provinceCode']==pc, lambda t:t['regionCode']==rc, lambda t:True):
        hit=[t for t in c if f(t)]
        if len(hit)==1: return hit[0]
    return None
def rows(f):
    b=ET.fromstring(zipfile.ZipFile(f).read('word/document.xml')).find(W+'body')
    tbls=[t for t in b.iter(W+'tbl') if 'AFFECTED' in txt(t.findall(W+'tr')[0]).upper()]
    t=max(tbls,key=lambda t:len(t.findall(W+'tr')))
    for r in t.findall(W+'tr'):
        cs=r.findall(W+'tc'); v=[txt(c) for c in cs]
        span=cs[0].find(W+'tcPr/'+W+'gridSpan') is not None
        yield v,span
for f in sys.argv[1:]:
    rc=pc=None; stats={'region':[0,0],'province':[0,0],'town':[0,0]}; miss=[]
    for v,span in rows(f):
        if not any(re.fullmatch(r'[\d,.\-]+',x) for x in v[1:]) or 'TOTAL' in v[0].upper(): continue
        if span and v[0]:
            name=v[0]; k=norm(name)
            if k in reg: rc=reg[k]; pc=None; stats['region'][0]+=1; continue
            if k in prov:
                p=[p for p in prov[k] if p['regionCode']==rc] or prov[k]; pc=p[0]['code']; rc=p[0]['regionCode']; stats['province'][0]+=1; continue
            if rc=='130000000' or find_town(name,None,rc):  # NCR city / HUC listed at province level
                t=find_town(name,None,rc); stats['town'][0 if t else 1]+=1
                if not t: miss.append(('town@prov',name))
                continue
            stats['province'][1]+=1; miss.append(('prov?',name))
        elif not v[0] and len(v)>1 and v[1]:
            t=find_town(v[1],pc,rc); stats['town'][0 if t else 1]+=1
            if not t: miss.append(('town',v[1],[x['name'] for x in towns.get(norm(v[1]),[])][:3]))
    print('==',f,{k:f'{a} matched / {b} missed' for k,(a,b) in stats.items()})
    for m in miss: print('   MISS',m)
