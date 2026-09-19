import requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'}
# proxy.cc api guesses
for u in [
 'https://proxy.cc/api/free-proxy/api/1.0?country=all&limit=20',
 'https://proxy.cc/api/free-proxy',
 'https://proxy.cc/api/proxy/free?limit=20',
 'https://www.proxy.cc/api/free-proxy/export?format=json',
 'https://proxy.cc/zh/freeproxy/?export=json',
]:
 try:
  r=requests.get(u,headers=UA,timeout=10,verify=False)
  print(u, r.status_code, r.headers.get('content-type',''), len(r.content), r.text[:120].replace('\n',' '))
 except Exception as e:
  print(u, 'ERR', type(e).__name__, str(e)[:100])
# proxifly backend guesses
for u in [
 'https://proxifly.dev/api/proxy-list?type=http&format=txt&limit=20',
 'https://backend.proxifly.dev/proxy-list?protocol=http&perPage=20',
 'https://proxifly.dev/b/proxy-list?type=http',
]:
 try:
  r=requests.get(u,headers=UA,timeout=10,verify=False)
  print(u, r.status_code, r.headers.get('content-type',''), len(r.content), r.text[:120].replace('\n',' '))
 except Exception as e:
  print(u, 'ERR', type(e).__name__, str(e)[:100])
# netvortex php api
ur=['https://net-vortex.com/api/free_proxies.php','https://net-vortex.com/api/free_proxies.php?limit=20','https://api.net-vortex.com/free-proxies']
for u in ur:
 try:
  r=requests.get(u,headers=UA,timeout=10,verify=False)
  print(u, r.status_code, r.headers.get('content-type',''), len(r.content), r.text[:150].replace('\n',' '))
 except Exception as e:
  print(u, 'ERR', type(e).__name__, str(e)[:100])
