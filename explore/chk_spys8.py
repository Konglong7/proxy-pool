import re
body = open('raw/spys.one.html', encoding='utf-8', errors='ignore').read()
scripts = list(re.finditer(r'<script[^>]*>(.*?)</script>', body, re.S))
for i in range(0, 10):
    s = scripts[i].group(1).strip()
    print(f'=== script {i}: len {len(s)} ===')
    print(s[:1200].replace('\n',' '))
    print()
