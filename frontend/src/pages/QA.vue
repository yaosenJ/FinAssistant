<template>
  <div class="wrap">
    <el-card>
      <h3>金融投教问答</h3>
      <el-form :inline="true" class="mb">
        <el-form-item>
          <el-input v-model="question" placeholder="请输入问题，如：什么是PEG？" style="width: 520px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onAsk">提问</el-button>
        </el-form-item>
      </el-form>

      <el-empty v-if="!answer && !loading" description="请输入问题并提问" />

      <el-skeleton :loading="loading" animated :throttle="300">
        <template #default>
          <div v-if="answer">
            <el-card class="mb">
              <h4>回答</h4>
              <div>{{ answer.answer }}</div>
            </el-card>
            <el-card>
              <h4>参考来源</h4>
              <el-link v-for="(s, idx) in answer.sources" :key="idx" :href="s.url" target="_blank" class="src">{{ s.title }}</el-link>
            </el-card>
          </div>
        </template>
      </el-skeleton>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { finQA } from '@/services/features'

const question = ref('')
const loading = ref(false)
const answer = ref<null | { answer: string; sources: Array<{ title: string; url: string }> }>(null)

async function onAsk() {
  if (!question.value) return
  loading.value = true
  try {
    const res = await finQA(question.value)
    answer.value = { answer: res.answer, sources: res.sources }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.wrap { padding: 12px; }
.mb { margin-bottom: 12px; }
.src { display: block; margin: 6px 0; }
</style>
