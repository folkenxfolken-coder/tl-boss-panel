import re, requests, urllib.parse

START='https://cdn.questlog.gg/_static/throne-and-liberty/_nuxt/C_BOSu9B.js'
seen=set(); queue=[START]
needles=['AMERICAS','fieldBoss','rotation','triggerTimes','Ascended Junobote','Pakilo Naru']

while queue and len(seen)<120:
    url=queue.pop(0)
    if url in seen: continue
    seen.add(url)
    try:
        r=requests.get(url,timeout=20)
        print('FETCH',r.status_code,len(r.content),url)
        if not r.ok: continue
        text=r.text
        hits=[n for n in needles if n.lower() in text.lower()]
        if hits:
            print('HITS',hits,url)
            for n in hits:
                low=text.lower(); idx=low.find(n.lower())
                print('SNIP',n,text[max(0,idx-2500):idx+8000])
        for imp in re.findall(r'(?:from|import)\s*[\(]?\s*["\'](\.\/[^"\']+\.js)["\']',text):
            nxt=urllib.parse.urljoin(url,imp)
            if nxt not in seen: queue.append(nxt)
        # minified static imports can also appear as bare quoted ./X.js
        for imp in re.findall(r'["\'](\.\/[A-Za-z0-9_\-]+\.js)["\']',text):
            nxt=urllib.parse.urljoin(url,imp)
            if nxt not in seen: queue.append(nxt)
    except Exception as e:
        print('ERR',url,repr(e))
print('DONE',len(seen))
