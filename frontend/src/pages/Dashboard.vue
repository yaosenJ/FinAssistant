<template>
  <div class="wrap">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card>
          <div class="kpi">
            <div class="num">1,284</div>
            <div class="desc">今日入库新闻</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div class="kpi">
            <div class="num">98.2%</div>
            <div class="desc">召回率 (样例)</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <div class="kpi">
            <div class="num">342ms</div>
            <div class="desc">平均检索耗时</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-card class="mt">
      <h3>系统概览</h3>
      <p>展示近期数据入库、检索与重排的概况（演示占位）。</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.wrap { padding: 12px; }
.kpi { text-align: center; padding: 16px 0; }
.num { font-size: 28px; font-weight: 700; }
.desc { color: #888; }
.mt { margin-top: 16px; }
</style>
