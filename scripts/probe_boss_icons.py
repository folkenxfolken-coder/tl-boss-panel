import requests

PATH='assets/Game/Image/MapIcon/DE/WM_FB_ElderTurncoat_Target.WM_FB_ElderTurncoat_Target'
BASES=[
 'https://questlog.gg/throne-and-liberty/',
 'https://cdn.questlog.gg/throne-and-liberty/',
 'https://cdn.questlog.gg/_static/throne-and-liberty/',
 'https://assets.questlog.gg/throne-and-liberty/',
 'https://questlog.gg/',
]
SUFFIXES=['','.png','.webp','.jpg']

for base in BASES:
    for suffix in SUFFIXES:
        url=base+PATH+suffix
        try:
            r=requests.get(url,timeout=20,allow_redirects=True)
            print('TRY',r.status_code,r.headers.get('content-type'),len(r.content),r.url)
            if r.ok and (r.headers.get('content-type') or '').startswith('image/'):
                print('SUCCESS',url)
        except Exception as e:
            print('ERR',url,repr(e))
