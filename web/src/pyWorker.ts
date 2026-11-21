/// <reference lib="webworker" />

type PyRuntime = {
  loadPackage: (names: string[]) => Promise<void>
  unpackArchive: (data: Uint8Array, format: string) => void
  runPython: (code: string) => string
  globals: { set: (name: string, value: string) => void }
}
const runtime = (async () => {
  const url = 'https://cdn.jsdelivr.net/pyodide/v314.0.8/full/pyodide.mjs'
  const { loadPyodide } = await import(/* @vite-ignore */ url) as {
    loadPyodide: (options: { indexURL: string }) => Promise<PyRuntime>
  }
  const py = await loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v314.0.8/full/' })
  await py.loadPackage(['numpy', 'pydantic'])
  const response = await fetch(`${import.meta.env.BASE_URL}py/jurent_bundle.zip`)
  if (!response.ok) throw new Error('bundle unavailable')
  py.unpackArchive(new Uint8Array(await response.arrayBuffer()), 'zip')
  py.runPython("import sys; sys.path.insert(0, '/')")
  return py
})()

self.onmessage = async (event: MessageEvent<{ id: number; path: string; body: unknown }>) => {
  const { id, path, body } = event.data
  try {
    const py = await runtime
    py.globals.set('request_json', JSON.stringify({ path, body }))
    const output = py.runPython(`
import json
from urllib.parse import parse_qs, urlsplit
from src.jurent import service
request = json.loads(request_json)
url = urlsplit(request['path'])
try:
    if url.path == '/api/meta':
        result = service.meta()
    elif url.path == '/api/judge':
        result = service.judge(request['body'])
    elif url.path == '/api/explain':
        result = service.explain_rule(request['body'])
    elif url.path == '/api/budget':
        result = service.budget(request['body'])
    elif url.path == '/api/compare':
        query = parse_qs(url.query, keep_blank_values=True)
        rate = float(query['rate_pct'][0]) if 'rate_pct' in query else None
        result = service.compare(rate, query.get('school', [None])[0])
    else:
        raise ValueError('Unknown endpoint')
    reply = {'status': 200, 'body': result}
except service.InputError as exc:
    reply = {'status': 422, 'body': {'detail': str(exc)}}
except ValueError:
    reply = {'status': 422, 'body': {'detail': service.FORMAT_ERROR}}
json.dumps(reply, ensure_ascii=False)
`)
    const reply = JSON.parse(output) as { status: number; body: unknown }
    self.postMessage({ id, ...reply })
  } catch {
    self.postMessage({ id, status: 503, body: { detail: '계산 도구를 불러오지 못했어요. 인터넷 연결을 확인하고 새로 고침해 주세요' } })
  }
}
