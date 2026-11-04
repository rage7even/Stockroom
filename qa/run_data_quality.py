import csv
import json
from pathlib import Path
from qa.django_support import JsonClient, isolated_database
from backend.api import attempts

root=Path(__file__).resolve().parent
results=[]
for record in json.loads((root/'data_quality_cases.json').read_text()):
    with isolated_database():
        attempts.clear()
        client=JsonClient()
        client.post('/api/auth/login',data={'login':'manager@stockroom.local','password':'Stockroom2026!'})
        payload={'customer_id':record['customer_id'],'channel':record['channel'],'lines':record.get('lines',[{'sku':record['sku'],'qty':record['qty']}])}
        response=client.post('/api/orders',data=payload)
        results.append([record['id'],record.get('problem','Valid order'),record['expected'],response.status_code,'PASS' if response.status_code==record['expected'] else 'FAIL'])
with (root/'data_quality_results.csv').open('w',newline='',encoding='utf-8') as file:
    writer=csv.writer(file);writer.writerow(['ID','Case','Expected HTTP','Actual HTTP','Result']);writer.writerows(results)
for row in results: print(' | '.join(map(str,row)))
raise SystemExit(0 if all(row[-1]=='PASS' for row in results) else 1)
