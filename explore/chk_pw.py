# playwright chromium availability
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    try:
        b = p.chromium.launch(headless=True)
        print('chromium OK')
        b.close()
    except Exception as e:
        print('chromium MISSING:', str(e)[:200])
