import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import socket
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import httpx

root=Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as folder:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    env={**os.environ,'STOCKROOM_DB':str(Path(folder)/'smoke.db'),'STOCKROOM_DEMO':'1'}
    log=open(Path(folder)/'server.log','w')
    server=subprocess.Popen([sys.executable,'manage.py','run_stockroom',f'127.0.0.1:{port}','--noreload'],cwd=root,env=env,stdout=log,stderr=log)
    base=f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(base_url=base,timeout=10,trust_env=False) as client:
            for attempt in range(100):
                try:
                    if client.get('/api/health').status_code==200:break
                except httpx.ConnectError:pass
                time.sleep(.1)
            else:raise RuntimeError('Server did not start')
            response=client.get('/')
            assert response.status_code==200 and '<app-root>' in response.text
            for asset in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"',response.text):
                assert client.get('/'+asset.lstrip('/')).status_code==200
            assert '<app-root>' in client.get('/products').text
            assert client.get('/api/unknown').status_code==404
            assert client.post('/api/auth/login',json={'login':'manager@stockroom.local','password':'Stockroom2026!'}).status_code==200
            cookie=client.cookies.get('stockroom_session')
            def worker(i):
                with httpx.Client(base_url=base,cookies={'stockroom_session':cookie},timeout=10,trust_env=False) as reader:
                    times=[]
                    for j in range(5):
                        start=time.perf_counter();r=reader.get('/api/products');elapsed=time.perf_counter()-start
                        assert r.status_code==200 and len(r.json())==18
                        times.append(elapsed)
                    return times
            with ThreadPoolExecutor(max_workers=20) as pool:
                durations=[duration for batch in pool.map(worker,range(20)) for duration in batch]
            p95=sorted(durations)[94]
            report={'date':datetime.now(ZoneInfo('Asia/Qyzylorda')).date().isoformat(),'transport':'Real HTTP on loopback; Django run_stockroom subprocess','concurrent_clients':20,'availability_requests':100,'p95_seconds':round(p95,4),'nfr_target_seconds':1.5,'result':'PASS' if p95<=1.5 else 'FAIL','static_frontend_served':True,'limitations':'Local synthetic dataset only. Not a production/network benchmark; browser end-to-end not covered.'}
            (root/'qa'/'http_smoke_results.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
            assert p95<=1.5
    finally:
        # Windows venv launchers may spawn a child interpreter; stop our full test tree.
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(server.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            server.terminate()
        server.wait(timeout=10)
        log.close()
