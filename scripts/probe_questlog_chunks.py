import requests
url='https://throneandliberty.gameslantern.com/api/calendar?server=207'
r=requests.get(url,timeout=30)
print('STATUS',r.status_code,r.headers.get('content-type'))
print(r.text[:60000])
