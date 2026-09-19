import requests, re, urllib3
urllib3.disable_warnings()
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'}
for u in ['http://www.proxylistfree.com/', 'https://www.proxydb.net/anonymous', 'https://proxy.cc/zh/freeproxy/']:
    try:
        r = requests.get(u, headers=UA, timeout=25, verify=False, proxies={'http':None,'https':None})
        print(u, r.status_code, len(r.text), r.text[:120].replace('\n',' '))
        if 'proxylistfree' in u: open('raw/proxylistfree.html','w',encoding='utf-8').write(r.text)
        if 'proxydb' in u: open('raw/proxydb.html','w',encoding='utf-8').write(r.text)
        if 'proxy.cc' in u: open('raw/proxycc3.html','w',encoding='utf-8').write(r.text)
    except Exception as e:
        print(u, 'ERR', type(e).__name__, str(e)[:120])
