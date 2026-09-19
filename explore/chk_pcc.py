import re, base64, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'}
# save proxy.cc raw
r = requests.get('https://proxy.cc/zh/freeproxy/', headers=UA, timeout=25, verify=False)
body = r.text
open('raw/proxycc.html','w',encoding='utf-8').write(body)
print('proxy.cc saved', len(body))
# find api endpoints
for pat in [r'/api/[\w/?.=&%-]+', r'https?://[^\"\' ]*api[^\"\' ]*', r'free-proxy[\w/?.=&%-]*', r'__NUXT_DATA__|data-capo|fetch\(|useFetch|\$fetch']:
    found = sorted(set(re.findall(pat, body)))[:15]
    print(pat, '->', found)
# look for ip:port in body
ipp = set(re.findall(r'\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}', body))
print('proxy.cc ip:port count:', len(ipp), list(ipp)[:5])
