import sys,re,json,urllib.request,collections
from concurrent.futures import ThreadPoolExecutor
sys.stdout.reconfigure(encoding='utf-8')
d=json.load(open(sys.argv[1],encoding='utf-8'))
pat=re.compile(r'Typhoon|Tropical Storm|Tropical Depression|Southwest Monsoon|Habagat',re.I)
posts={}
for y in sorted(d):
    if int(y)<2017: continue
    for u,t in d[y].items():
        if pat.search(t) and 'intertropical' not in t.lower() and u not in posts: posts[u]=(y,t)
def fetch(u):
    for _ in range(3):
        try: return urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read().decode('utf-8','replace')
        except Exception: pass
def work(u):
    h=fetch(u)
    if h is None: return u,None
    site=[l for l in dict.fromkeys(re.findall(r'href="([^"]+\.(?:pdf|docx?|xlsx?))"',h,re.I)) if '/wp-content/uploads/' in l]
    g=list(dict.fromkeys(re.findall(r'href="(https://(?:docs|drive)\.google\.com/[^"]+)"',h)))
    return u,{'site':site,'google':g}
with ThreadPoolExecutor(6) as ex: res=dict(ex.map(work,posts))
out={u:{'year':posts[u][0],'title':posts[u][1],**(res[u] or {'failed':True})} for u in posts}
json.dump(out,open('filecount.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
by=collections.defaultdict(lambda:[0,0,0,0,0])
for u,v in out.items():
    b=by[v['year']]; b[0]+=1
    if v.get('failed'): b[4]+=1; continue
    b[1]+=len(v['site']); b[2]+=len(v['google'])
    b[3]+=sum(1 for l in v['site'] if l.lower().endswith('.pdf'))
print('year posts site_files google_links pdfs failed')
for y in sorted(by): print(y,*by[y])
print('TOTAL',*[sum(b[i] for b in by.values()) for i in range(5)])
print('zero-file posts:',[v['title'][:50] for v in out.values() if not v.get('failed') and not v['site'] and not v['google']])
