<template>
  <div class="center">
    <el-card class="card">
      <h2>登录 FinAssistant</h2>
      <el-form :model="form" @keyup.enter="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSubmit" :loading="loading">登录</el-button>
          <el-button link @click="$router.push({name:'register'})">去注册</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useAuthStore } from '@/store/auth'
import { useRoute, useRouter } from 'vue-router'
import { login, me } from '@/services/auth'

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

async function onSubmit() {
  loading.value = true
  try {
    const { token } = await login(form.username, form.password)
    // 获取用户信息
    auth.setToken(token)
    const profile = await me()
    auth.loginWithProfile({ id: String(profile.id), username: profile.username, role: profile.role }, token)
    const redirect = (route.query.redirect as string) || '/'
    router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.center { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { width: 360px; }
</style>
