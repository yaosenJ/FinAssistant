<template>
  <div class="center">
    <el-card class="card">
      <h2>注册账号</h2>
      <el-form :model="form" @keyup.enter="onSubmit">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="例如: analyst01" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" placeholder="选择角色">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSubmit" :loading="loading">注册</el-button>
          <el-button link @click="$router.push({name:'login'})">返回登录</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { register } from '@/services/auth'
import { useRouter } from 'vue-router'

const form = reactive({ username: '', password: '', role: 'user' as 'user' | 'admin' })
const loading = ref(false)
const router = useRouter()

async function onSubmit() {
  loading.value = true
  try {
    await register(form.username, form.password, form.role)
    router.push({ name: 'login' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.center { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.card { width: 420px; }
</style>
