import truststore
truststore.inject_into_ssl()
import requests, time

query = '[out:json][timeout:15];(nwr["amenity"="hospital"](around:5000,28.6139,77.2090););out center;'
headers = {'User-Agent': 'leadgenerator/1.0 (nearby-business-fallback)'}

print("--- Test 1: POST data=dict, verify=True (truststore) ---")
start = time.time()
try:
    r = requests.post('https://overpass-api.de/api/interpreter',
                      data={'data': query}, headers=headers, timeout=(8, 20), verify=True)
    print(f'Status: {r.status_code} | Time: {time.time()-start:.1f}s')
    print(f'Body[:200]: {r.text[:200]}')
except Exception as e:
    print(f'FAILED in {time.time()-start:.1f}s: {e}')

print()
print("--- Test 2: GET params, verify=True (truststore) ---")
start = time.time()
try:
    r = requests.get('https://overpass-api.de/api/interpreter',
                     params={'data': query}, headers=headers, timeout=(8, 20), verify=True)
    print(f'Status: {r.status_code} | Time: {time.time()-start:.1f}s')
    print(f'Body[:200]: {r.text[:200]}')
    if r.ok:
        print(f'Elements: {len(r.json().get("elements", []))}')
except Exception as e:
    print(f'FAILED in {time.time()-start:.1f}s: {e}')
