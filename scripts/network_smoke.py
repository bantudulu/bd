from __future__ import annotations
import statistics, sys, time
import httpx

BASE=(sys.argv[1] if len(sys.argv)>1 else "https://bantudulu.vercel.app").rstrip("/")
ROUTES=["/healthz","/masuk","/loading","/openapi.json"]
RUNS=3
WARN_MS=1500.0

def percentile(values,p):
    values=sorted(values)
    if not values:return 0.0
    idx=min(len(values)-1,max(0,round((len(values)-1)*p)))
    return values[idx]

failed=False
with httpx.Client(timeout=15.0,follow_redirects=True) as client:
    for route in ROUTES:
        samples=[]; status=0
        for _ in range(RUNS):
            t=time.perf_counter()
            r=client.get(BASE+route,headers={"Cache-Control":"no-cache"})
            samples.append((time.perf_counter()-t)*1000); status=r.status_code
        p50=statistics.median(samples); p95=percentile(samples,0.95)
        flag="WARN" if p95>WARN_MS else "PASS"
        if status>=500: flag="FAIL"; failed=True
        print(f"{route:16} HTTP {status} p50={p50:.0f}ms p95={p95:.0f}ms {flag}")
if failed: raise SystemExit(1)
