import concurrent.futures
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
    db = Path(folder) / "check.db"
    shutil.copy2(root / "database/demo.db", db)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log = open(Path(folder) / "server.log", "w")
    proc = subprocess.Popen(
        [
            sys.executable,
            str(root / "backend/manage.py"),
            "runserver",
            f"127.0.0.1:{port}",
            "--noreload",
        ],
        env={**os.environ, "STOCKROOM_DB": str(db)},
        stdout=log,
        stderr=log,
    )
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar)
    )
    try:
        for i in range(100):
            try:
                opener.open(base + "/api/auth/csrf")
                break
            except urllib.error.URLError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Server did not start")

        def token():
            return next(c.value for c in jar if c.name == "csrftoken")

        def call(path, body=None):
            request = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json", "X-CSRFToken": token()},
            )
            try:
                with opener.open(request) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        assert (
            call(
                "/api/auth/login",
                {"login": "manager@stockroom.local", "password": "Stockroom2026!"},
            )[0]
            == 200
        )
        assert b"<app-root>" in opener.open(base + "/").read()
        cookies = "; ".join(c.name + "=" + c.value for c in jar)
        csrf = token()

        def request(path, body=None):
            op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={
                    "Content-Type": "application/json",
                    "Cookie": cookies,
                    "X-CSRFToken": csrf,
                },
            )
            try:
                with op.open(req) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                return e.code, e.read()

        def reader(i):
            times = []
            for j in range(5):
                start = time.perf_counter()
                status, body = request("/api/products")
                times.append(time.perf_counter() - start)
                assert status == 200 and len(json.loads(body)) == 18
            return times

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            times = [t for batch in pool.map(reader, range(20)) for t in batch]
        customer = json.loads(call("/api/customers")[1])[0]["customer_id"]

        def order(channel):
            return request(
                "/api/orders",
                {
                    "customer_id": customer,
                    "channel": channel,
                    "lines": [{"sku": "ANK-C20W-WHT", "qty": 4}],
                },
            )[0]

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            race = sorted(pool.map(order, ["website", "sales_manager"]))
        assert race == [201, 409], race
        p95 = sorted(times)[94]
        report = {
            "date": "2026-11-06",
            "real_HTTP": True,
            "frontend_served": True,
            "clients": 20,
            "reads": 100,
            "p95_seconds": round(p95, 4),
            "target_seconds": 1.5,
            "performance_pass": p95 <= 1.5,
            "simultaneous_order_statuses": race,
            "browser_end_to_end": "NOT RUN",
            "platform": "Linux; Windows batch not executed",
        }
        assert p95 <= 1.5
        (root / "qa/http_results.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        proc.terminate()
        proc.wait(timeout=10)
        log.close()
