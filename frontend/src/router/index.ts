import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/store/auth'

const Login = () => import('@/pages/Login.vue')
const Register = () => import('@/pages/Register.vue')
const Dashboard = () => import('@/pages/Dashboard.vue')
const Research = () => import('@/pages/Research.vue')
const StockDiagnosis = () => import('@/pages/StockDiagnosis.vue')
const Indices = () => import('@/pages/Indices.vue')
const QA = () => import('@/pages/QA.vue')
const AdminUsers = () => import('@/pages/AdminUsers.vue')
const Shell = () => import('@/pages/Shell.vue')

const routes: Array<RouteRecordRaw> = [
  { path: '/login', name: 'login', component: Login, meta: { public: true } },
  { path: '/register', name: 'register', component: Register, meta: { public: true } },
  {
    path: '/',
    component: Shell,
    children: [
      { path: '', name: 'dashboard', component: Dashboard },
      { path: 'research', name: 'research', component: Research },
      { path: 'stocks', name: 'stocks', component: StockDiagnosis },
      { path: 'indices', name: 'indices', component: Indices },
      { path: 'qa', name: 'qa', component: QA },
      { path: 'admin/users', name: 'admin-users', component: AdminUsers, meta: { role: 'admin' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) return next()
  if (!auth.isAuthenticated) return next({ name: 'login', query: { redirect: to.fullPath } })
  if (to.meta.role && !auth.hasRole(String(to.meta.role))) return next({ name: 'dashboard' })
  next()
})

export default router
