import axios from 'axios'
import { useAuthStore } from '@/store/auth'

const baseURL = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000'

export const http = axios.create({ baseURL })

http.interceptors.request.use((config) => {
  try {
    const auth = useAuthStore()
    if (auth.isAuthenticated) {
      config.headers = config.headers || {}
      config.headers['Authorization'] = `Bearer ${auth.currentUser?.token}`
    }
  } catch {}
  return config
})

http.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response && err.response.status === 401) {
      try { useAuthStore().logout() } catch {}
    }
    return Promise.reject(err)
  }
)
