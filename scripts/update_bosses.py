import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path("site/boss-data.json")
PAGE = "https://questlog.gg/throne-and-liberty/en/event-calendar"


async def main():
    matches = []
    api_hits = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="en-US",
            timezone_id="America/Santiago",
            viewport={"width":1440,"height":1600},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        await page.add_init_script("try{localStorage.setItem('tl-rain-schedule-region','AMERICAS')}catch(e){}")

        async def on_response(resp):
            try:
                u = resp.url
                low = u.lower()
                ctype = (resp.headers.get('content-type') or '').lower()
                if 'questlog.gg/throne-and-liberty/api/' in low and any(k in low for k in ('eventcalendar','calendar','boss','schedule','event')):
                    txt = await resp.text() if any(x in ctype for x in ('json','text','javascript')) else ''
                    api_hits.append((u, txt[:5000]))
                if 'questlog.gg' in low and ('javascript' in ctype or low.endswith('.js')):
                    txt = await resp.text()
                    if any(k.lower() in txt.lower() for k in ('getFieldBossEntries','Upcoming Field Bosses','fieldBossEntries','fieldBossSchedule','field boss')):
                        for needle in ('getFieldBossEntries','Upcoming Field Bosses','fieldBossEntries','fieldBossSchedule'):
                            idx = txt.find(needle)
                            if idx >= 0:
                                matches.append((u, needle, txt[max(0,idx-5000):idx+12000]))
            except Exception as exc:
                print('RESP_ERR', repr(exc))

        page.on('response', on_response)
        await page.goto(PAGE, wait_until='domcontentloaded', timeout=90000)
        await page.wait_for_timeout(15000)
        resources = await page.evaluate("() => performance.getEntriesByType('resource').map(x=>x.name).filter(x=>x.includes('questlog.gg'))")
        print('RESOURCE_COUNT', len(resources))
        print('API_COUNT', len(api_hits))
        for u, body in api_hits:
            print('QL_API', u)
            if body:
                print('QL_API_BODY', body)
        print('JS_MATCH_COUNT', len(matches))
        seen = set()
        for u, needle, snippet in matches:
            key=(u,needle)
            if key in seen: continue
            seen.add(key)
            print('JS_MATCH_URL', u)
            print('JS_MATCH_NEEDLE', needle)
            print('JS_SNIPPET_BEGIN')
            print(snippet)
            print('JS_SNIPPET_END')
        await browser.close()

    payload={
        'source':'Questlog diagnostic',
        'updated_at':datetime.now(timezone.utc).isoformat(),
        'fallback':False,
        'model':'questlog-diagnostic-v5',
        'region':'Americas',
        'timezone':'America/Santiago',
        'slots':[]
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    asyncio.run(main())
