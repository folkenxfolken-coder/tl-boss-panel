import asyncio
from playwright.async_api import async_playwright

PAGES = {
    'Morokai':'https://questlog.gg/throne-and-liberty/en/db/event/640E381B26130F81',
    'Leviathan':'https://questlog.gg/throne-and-liberty/en/db/npc/FD_L04_M_MudShark_Leviathan_002',
}

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width':1400,'height':1200})
        for name,url in PAGES.items():
            image_urls=[]
            def on_resp(resp):
                try:
                    ct=(resp.headers.get('content-type') or '').lower()
                    if ct.startswith('image/'):
                        image_urls.append(resp.url)
                except Exception:
                    pass
            page.on('response',on_resp)
            print('PAGE',name,url)
            await page.goto(url,wait_until='networkidle',timeout=90000)
            await page.wait_for_timeout(3000)
            imgs = await page.eval_on_selector_all('img', "els => els.map(x => ({src:x.src,alt:x.alt||'',w:x.naturalWidth,h:x.naturalHeight})).filter(x=>x.src)")
            for x in imgs:
                print('IMG',name,x)
            bgs = await page.evaluate("""() => [...document.querySelectorAll('*')].map(el => {
              const bg=getComputedStyle(el).backgroundImage;
              return bg && bg !== 'none' ? {tag:el.tagName,cls:el.className||'',bg} : null;
            }).filter(Boolean).filter(x=>x.bg.includes('url('))""")
            for x in bgs:
                if 'questlog' in x['bg'] or 'assets' in x['bg'] or 'plaync' in x['bg']:
                    print('BG',name,x)
            for u in sorted(set(image_urls)):
                if any(k in u.lower() for k in ('mapicon','boss','field','event','assets/game/image')):
                    print('NETIMG',name,u)
            page.remove_listener('response',on_resp)
        await browser.close()

if __name__=='__main__':
    asyncio.run(main())
