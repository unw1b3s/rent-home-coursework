"""Запустить сервер, затем python scripts/benchmark.py. Результат — docs/benchmark.json."""
import json
import platform
import statistics
import time
import urllib.request
from pathlib import Path

url='http://127.0.0.1:8000/api/listings'
for _ in range(5):
    with urllib.request.urlopen(url) as response:
        records=json.load(response)['total']
samples=[]
for _ in range(100):
    start=time.perf_counter()
    with urllib.request.urlopen(url) as response:
        assert response.status==200
        response.read()
    samples.append((time.perf_counter()-start)*1000)
result={'date':time.strftime('%Y-%m-%d'),'endpoint':'GET /api/listings','requests':100,'concurrency':1,
        'warmup':5,'records':records,'environment':f'{platform.system()} {platform.machine()}, Python {platform.python_version()}, Uvicorn, loopback HTTP',
        'mean_ms':round(statistics.mean(samples),2),'p95_ms':round(sorted(samples)[94],2),
        'max_ms':round(max(samples),2),'notes':'Локальный последовательный замер; не нагрузочное тестирование.'}
Path(__file__).resolve().parents[1].joinpath('docs/benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
