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
            print('PAGE',name,url)
            await page.goto(url,wait_until='domcontentloaded',timeout=90000)
            await page.wait_for_timeout(5000)
            imgs = await page.eval_on_selector_all('img', "els => els.map(x => ({src:x.src,alt:x.alt||'',w:x.naturalWidth,h:x.naturalHeight})).filter(x=>x.src)")
            for x in imgs:
                if x['w']>=32 and x['h']>=32:
                    print('IMG',name,x)
        await browser.close()

if __name__=='__main__':
    asyncio.run(main())
