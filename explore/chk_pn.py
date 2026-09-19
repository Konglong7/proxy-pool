import re, base64
body = open('raw/proxynova.html', encoding='utf-8', errors='ignore').read()
writes = re.findall(r'document\.write\([^)]*\)', body)
print('proxynova document.write count:', len(writes))
print('sample scripts:')
for w in writes[:6]:
    print('  ', w[:200])
# check atob patterns
atobs = re.findall(r'atob\("[^"]{2,}"\)', body)
print('atob count:', len(atobs), 'samples:', atobs[:5])
