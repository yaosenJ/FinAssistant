<template>
  <div class="wrap">
    <el-card>
      <h3>板块指数概览</h3>
      <el-radio-group v-model="kind" size="small" class="mb">
        <el-radio-button label="industry">行业板块</el-radio-button>
        <el-radio-button label="concept">概念板块</el-radio-button>
      </el-radio-group>

      <el-table :data="items" border>
        <el-table-column prop="name" label="板块" />
        <el-table-column prop="change" label="涨跌幅%" width="120">
          <template #default="{ row }">
            <span :style="{ color: row.change >= 0 ? '#d03050' : '#2d8cf0' }">{{ row.change.toFixed(2) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="leaders" label="龙头" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, watchEffect } from 'vue'
import { indicesOverview } from '@/services/features'

const kind = ref<'industry' | 'concept'>('industry')
const items = ref<Array<{ name: string; change: number; leaders: string[] }>>([])

watchEffect(async () => {
  const data = await indicesOverview(kind.value)
  items.value = data.items
})
</script>

<style scoped>
.wrap { padding: 12px; }
.mb { margin-bottom: 12px; }
</style>
