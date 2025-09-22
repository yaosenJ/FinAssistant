import { defineStore } from 'pinia'

export type User = {
  id: string
  username: string
  role: 'user' | 'admin'
  token: string
}

function loadUser(): User | null {
  const raw = localStorage.getItem('fa_user')
  return raw ? JSON.parse(raw) as User : null
}

function saveUser(user: User | null) {
  if (user) localStorage.setItem('fa_user', JSON.stringify(user))
  else localStorage.removeItem('fa_user')
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    currentUser: loadUser() as User | null
  }),
  getters: {
    isAuthenticated: (s) => !!s.currentUser,
    username: (s) => s.currentUser?.username ?? '',
    role: (s) => s.currentUser?.role ?? 'user'
  },
  actions: {
    setToken(token: string) {
      if (this.currentUser) {
        this.currentUser.token = token
        saveUser(this.currentUser)
      }
    },
    loginWithProfile(profile: { id: string; username: string; role: 'user' | 'admin' }, token: string) {
      this.currentUser = { ...profile, token }
      saveUser(this.currentUser)
    },
    logout() {
      this.currentUser = null
      saveUser(null)
    },
    hasRole(role: 'user' | 'admin') {
      return this.currentUser?.role === role
    }
  }
})
