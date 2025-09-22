import { http } from './http'
import { User } from '@/store/auth'

export async function login(username: string, password: string): Promise<{ token: string }> {
  const form = new URLSearchParams()
  form.set('username', username)
  form.set('password', password)
  const { data } = await http.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
  return { token: data.access_token as string }
}

export async function register(username: string, password: string, role: 'user' | 'admin') {
  await http.post('/auth/register', { username, password, role })
}

export async function me(): Promise<{ id: number; username: string; role: 'user' | 'admin' }> {
  const { data } = await http.get('/users/me')
  return data
}
