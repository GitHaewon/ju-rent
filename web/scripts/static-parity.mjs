import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { loadPyodide } from 'pyodide'

const root = join(import.meta.dirname, '../..')
const expected = JSON.parse(readFileSync(join(root, 'outputs/static/parity_expected.json'), 'utf8'))
const py = await loadPyodide()
await py.loadPackage(['numpy', 'pydantic'])
py.unpackArchive(new Uint8Array(readFileSync(join(root, 'web/public/py/jurent_bundle.zip'))), 'zip')
py.runPython("import sys; sys.path.insert(0, '/')")

function firstDifference(actual, expected, path = '$') {
  if (Object.is(actual, expected)) return null
  if (actual && expected && typeof actual === 'object' && typeof expected === 'object') {
    const keys = new Set([...Object.keys(actual), ...Object.keys(expected)])
    for (const key of keys) {
      const diff = firstDifference(actual[key], expected[key], `${path}.${key}`)
      if (diff) return diff
    }
    return null
  }
  return `${path}: ${JSON.stringify(actual)} != ${JSON.stringify(expected)}`
}

for (const [index, item] of expected.cases.entries()) {
  py.globals.set('request_json', JSON.stringify({ path: item.path, body: item.input }))
  const response = JSON.parse(py.runPython(`
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
    else:
        query = parse_qs(url.query, keep_blank_values=True)
        rate = float(query['rate_pct'][0]) if 'rate_pct' in query else None
        result = service.compare(rate, query.get('school', [None])[0])
    reply = {'status': 200, 'body': result}
except service.InputError as exc:
    reply = {'status': 422, 'body': {'detail': str(exc)}}
except ValueError:
    reply = {'status': 422, 'body': {'detail': service.FORMAT_ERROR}}
json.dumps(reply, ensure_ascii=False)
`))
  const difference = firstDifference(response, { status: item.status, body: item.body })
  if (difference) throw new Error(`case ${index}: ${item.path}: ${difference.slice(0, 500)}; body=${JSON.stringify(response.body).slice(0, 300)}`)
}
console.log(`Pyodide 314.0.8 exact parity: ${expected.cases.length} cases`)
