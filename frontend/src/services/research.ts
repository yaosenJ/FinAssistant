import { http } from './http'

export async function search(query: string, mode: 'vector' | 'hybrid' | 'rerank') {
  if (!query) return []
  const { data } = await http.get('/features/research', { params: { query, mode } })
  return data
}

export async function newsRecall(query: string, mode: 'vector' | 'bm25' | 'hybrid' = 'hybrid', limit = 10) {
  const { data } = await http.get('/news/recall', { params: { query, mode, limit } })
  return data
}
