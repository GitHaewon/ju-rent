// The only transport used by the UI: HTTP locally, Python Worker on Pages.

export const staticMode = import.meta.env.VITE_JU_RENT_MODE === 'static'

type Pending = { resolve: (value: Response) => void; reject: (reason: Error) => void; signal?: AbortSignal }
type WorkerReply = { id: number; status: number; body: unknown }
let worker: Worker | null = null
let nextId = 0
const pending = new Map<number, Pending>()

function getWorker(): Worker {
  if (worker) return worker
  worker = new Worker(new URL('./pyWorker.ts', import.meta.url), { type: 'module' })
  worker.onmessage = (event: MessageEvent<WorkerReply>) => {
    const { id, status, body } = event.data
    const request = pending.get(id)
    if (!request) return
    pending.delete(id)
    if (request.signal?.aborted) return
    request.resolve(new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }))
  }
  worker.onerror = () => {
    for (const request of pending.values()) request.reject(new Error('계산 도구를 불러오지 못했어요. 인터넷 연결을 확인하고 새로 고침해 주세요'))
    pending.clear()
  }
  return worker
}

export function backendFetch(path: string, init?: RequestInit): Promise<Response> {
  if (!staticMode) return fetch(path, init)
  if (init?.signal?.aborted) return Promise.reject(new DOMException('Aborted', 'AbortError'))
  const id = ++nextId
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject, signal: init?.signal ?? undefined })
    init?.signal?.addEventListener('abort', () => {
      pending.delete(id)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
    getWorker().postMessage({ id, path, body: init?.body ? JSON.parse(String(init.body)) : null })
  })
}
