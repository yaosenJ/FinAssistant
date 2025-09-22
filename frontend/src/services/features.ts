import { http } from './http'

export async function diagnoseStock(code: string) {
  const { data } = await http.get('/features/stocks/diagnosis', { params: { code } })
  return data as { code: string; rating: string; summary: string; factors: Record<string,string> }
}

export async function indicesOverview(kind: 'industry' | 'concept' = 'industry') {
  const { data } = await http.get('/features/indices/overview', { params: { kind } })
  return data as { kind: string; items: Array<{ name: string; change: number; leaders: string[] }> }
}

export async function finQA(question: string) {
  const { data } = await http.get('/features/qa', { params: { question } })
  return data as { question: string; answer: string; sources: Array<{ title: string; url: string }> }
}
