const BASE = '/api'

async function request(method, path, body) {
  const resp = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!resp.ok) {
    let detail = `${resp.status}`
    try {
      const data = await resp.json()
      detail = data.detail || JSON.stringify(data)
    } catch (e) { /* 保留状态码 */ }
    throw new Error(detail)
  }
  return resp.json()
}

export const api = {
  summary: (asOf) => request('GET', `/summary/${asOf ? `?as_of=${asOf}` : ''}`),
  contracts: () => request('GET', '/contracts/'),
  contract: (id) => request('GET', `/contracts/${id}/`),
  recognizePeriod: (id, period) =>
    request('POST', `/contracts/${id}/recognize_period/`, { period }),
  addPayment: (id, payload) => request('POST', `/contracts/${id}/payments/`, payload),
  addAcceptance: (lineId, payload) => request('POST', `/lines/${lineId}/acceptance/`, payload),
  addUsage: (lineId, payload) => request('POST', `/lines/${lineId}/usage/`, payload),
}

export function fmt(value) {
  const n = Number(value ?? 0)
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
