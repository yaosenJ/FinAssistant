import { http } from './http'

export type UserLite = { id: number; username: string; role: 'user' | 'admin' }

export async function listUsers(): Promise<UserLite[]> {
  const { data } = await http.get('/users/')
  return data
}

export async function createUser(payload: { username: string; password: string; role: 'user' | 'admin' }): Promise<UserLite> {
  const { data } = await http.post('/users/', payload)
  return data
}

export async function updateUser(payload: { id: number; username: string; role: 'user' | 'admin' }): Promise<UserLite> {
  const { data } = await http.put(`/users/${payload.id}`, { username: payload.username, role: payload.role })
  return data
}

export async function deleteUser(id: number): Promise<void> {
  await http.delete(`/users/${id}`)
}
