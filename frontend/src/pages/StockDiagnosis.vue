<template>
  <div class="wrap">
    <el-card>
      <h3>股票综合诊断</h3>
      <el-form :inline="true" class="mb">
        <el-form-item label="代码">
          <el-input v-model="code" placeholder="例如：600519" style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onFetch">诊断</el-button>
        </el-form-item>
      </el-form>

      <el-empty v-if="!result && !loading" description="请输入股票代码" />

      <el-skeleton :loading="loading" animated :throttle="300">
        <template #default>
          <div v-if="result">
            <el-result icon="success" :title="`评级：${result.rating}`" :sub-title="result.summary" />
            <el-descriptions title="关键因子" :column="2" border>
              <el-descriptions-item v-for="(v,k) in result.factors" :key="k" :label="k">{{ v }}</el-descriptions-item>
            </el-descriptions>
          </div>
        </template>
      </el-skeleton>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { diagnoseStock } from '@/services/features'

const code = ref('')
const loading = ref(false)
const result = ref<null | { code: string; rating: string; summary: string; factors: Record<string,string> }>(null)

async function onFetch() {
  if (!code.value) return
  loading.value = true
  try {
    result.value = await diagnoseStock(code.value)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.wrap { padding: 12px; }
.mb { margin-bottom: 12px; }
</style>
