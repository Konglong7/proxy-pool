# -*- coding: utf-8 -*-
"""Validate collected proxies concurrently and build per-site stats + final report."""
import os, re, json, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests, urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"}
CHECK_URL = "http://checkip.amazonaws.com/"
CHECK_URL_HTTPS = "https://checkip.amazonaws.com/"
SAMPLE_PER_SOURCE = 25
WORKERS = 50
TIMEOUT = 8

IPRE = re.compile(r"\d{1,3}(?:\.\d{1,3}){3}")


def test_proxy(ip_port):
    """Test one proxy: HTTP check first; then HTTPS tunnel check."""
    proxies = {"http": f"http://{ip_port}", "https": f"http://{ip_port}"}
    rec = {"ip_port": ip_port, "http_ok": False, "https_ok": False, "exit_ip": "", "ms": 0, "err": ""}
    t0 = time.time()
    try:
        r = requests.get(CHECK_URL, proxies=proxies, timeout=TIMEOUT, headers=UA, verify=False)
        ms = int((time.time() - t0) * 1000)
        rec["ms"] = ms
        if r.status_code == 200:
            m = IPRE.search(r.text or "")
            if m:
                rec["http_ok"] = True
                rec["exit_ip"] = m.group(0)
                t1 = time.time()
                try:
                    r2 = requests.get(CHECK_URL_HTTPS, proxies=proxies, timeout=TIMEOUT, headers=UA, verify=False)
                    if r2.status_code == 200 and IPRE.search(r2.text or ""):
                        rec["https_ok"] = True
                except Exception:
                    pass
                rec["ms"] = int((time.time() - t0) * 1000)
                return rec
            rec["err"] = "bad body"
        else:
            rec["err"] = f"HTTP {r.status_code}"
    except Exception as e:
        rec["err"] = type(e).__name__
    return rec


def main():
    collected = json.load(open(os.path.join(BASE, "collected.json"), encoding="utf-8"))

    # build test plan
    plan = []
    for source, items in collected.items():
        # keep entries
        ips = []
        seen = set()
        for it in items:
            ip_port = it.get("ip_port")
            if not ip_port or ip_port in seen:
                continue
            seen.add(ip_port)
            ips.append(ip_port)
        random.shuffle(ips)
        sample = ips[:SAMPLE_PER_SOURCE]
        plan.append({"source": source, "total": len(ips), "test": sample})

    results = {}
    all_jobs = []
    for entry in plan:
        for ip_port in entry["test"]:
            all_jobs.append((entry["source"], ip_port))

    print(f"total jobs: {len(all_jobs)}")
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(test_proxy, ip_port): (src, ip_port) for src, ip_port in all_jobs}
        done = 0
        for fut in as_completed(futs):
            src, ip_port = futs[fut]
            try:
                rec = fut.result()
            except Exception as e:
                rec = {"ip_port": ip_port, "http_ok": False, "https_ok": False, "err": str(e)[:80]}
            results.setdefault(src, []).append(rec)
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(all_jobs)} tested, {int(time.time()-t0)}s")

    # stats
    stats = []
    for entry in plan:
        src = entry["source"]
        recs = results.get(src, [])
        ok = [r for r in recs if r.get("http_ok")]
        okh = [r for r in ok if r.get("https_ok")]
        tested = len(recs)
        rate = (len(ok) / tested * 100) if tested else 0
        stats.append({
            "source": src,
            "candidates": entry["total"],
            "sampled": tested,
            "http_ok": len(ok),
            "https_ok": len(okh),
            "rate": round(rate, 1),
            "avg_ms": int(sum(r.get("ms", 0) for r in ok) / len(ok)) if ok else 0,
            "working": [r["ip_port"] for r in ok],
        })

    stats.sort(key=lambda s: (-s["http_ok"], -s["rate"]))

    with open(os.path.join(BASE, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, "results_raw.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)

    all_working = sorted({ip for s in stats for ip in s["working"]})
    with open(os.path.join(BASE, "all_working_proxies.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_working))

    print("\n==== SUMMARY ====")
    for s in stats:
        print(f"{s['source']:45s} cand={s['candidates']:5d} tested={s['sampled']:3d} "
              f"httpOK={s['http_ok']:3d} httpsOK={s['https_ok']:3d} rate={s['rate']:5.1f}% "
              f"avg={s['avg_ms']}ms")
    print("total unique working:", len(all_working))


if __name__ == "__main__":
    main()