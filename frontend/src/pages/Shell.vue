<template>
  <el-container class="full">
    <el-aside width="220px" class="aside">
      <div class="brand">FinAssistant</div>
      <el-menu :router="true" :default-active="$route.path">
        <el-menu-item index="/">仪表盘</el-menu-item>
        <el-menu-item index="/research">投研助手</el-menu-item>
        <el-menu-item index="/stocks">股票诊断</el-menu-item>
        <el-menu-item index="/indices">板块指数</el-menu-item>
        <el-menu-item index="/qa">投教问答</el-menu-item>
        <el-sub-menu index="/admin" v-if="isAdmin">
          <template #title>管理</template>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div />
        <div class="right">
          <span class="username">{{ username }}</span>
          <el-button size="small" @click="onLogout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

const username = computed(() => auth.username)
const isAdmin = computed(() => auth.role === 'admin')

function onLogout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<style scoped>
.full { height: 100vh; }
.aside { border-right: 1px solid #eee; padding: 12px; }
.brand { font-weight: 700; font-size: 18px; margin: 8px 0 16px; }
.header { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #eee; }
.right { display: flex; align-items: center; gap: 12px; }
.username { color: #666; }
</style>
