<template>
  <div class="wrap">
    <el-card>
      <h3>智能投研助手</h3>
      <el-form :inline="true" class="mb">
        <el-form-item>
          <el-input v-model="query" placeholder="请输入调研问题，如：AI对半导体行业的影响" style="width:520px" />
        </el-form-item>
        <el-form-item>
          <el-select v-model="mode" placeholder="检索模式" style="width:160px">
            <el-option label="向量检索" value="vector" />
            <el-option label="混合检索" value="hybrid" />
            <el-option label="重排 + 检索" value="rerank" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onSearch">检索</el-button>
        </el-form-item>
      </el-form>

      <el-empty v-if="!results.length && !loading" description="请先输入问题并检索" />

      <el-skeleton :loading="loading" animated :throttle="300">
        <template #template>
          <el-skeleton-item variant="text" style="width: 60%" />
          <el-skeleton-item variant="text" style="width: 50%" />
          <el-skeleton-item variant="text" style="width: 40%" />
        </template>
        <template #default>
          <el-timeline>
            <el-timeline-item v-for="(item, idx) in results" :key="idx" :timestamp="(item.score ?? 0).toFixed(3)">
              <el-card>
                <div class="title">{{ item.title }}</div>
                <div class="content">{{ item.content?.slice(0,160) }}</div>
                <div class="meta">{{ item.trade_date }} · {{ item.source }}</div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
        </template>
      </el-skeleton>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { search, newsRecall } from '@/services/research'

const query = ref('')
const mode = ref<'vector' | 'hybrid' | 'rerank'>('hybrid')
const loading = ref(false)
const results = ref<Array<any>>([])

async function onSearch() {
  loading.value = true
  try {
    // 通用检索
    const generic = await search(query.value, mode.value)
    // 新闻多路召回（hybrid）
    const news = await newsRecall(query.value, 'hybrid', 8)
    results.value = [...news, ...generic]
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.wrap { padding: 12px; }
.mb { margin-bottom: 12px; }
.title { font-weight: 600; margin-bottom: 6px; }
.content { color: #333; margin-bottom: 4px; }
.meta { color: #888; font-size: 12px; }
</style>
