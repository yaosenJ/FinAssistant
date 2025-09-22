<template>
  <div class="wrap">
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增用户</el-button>
        <el-input v-model="keyword" placeholder="搜索用户名" style="width: 220px" />
      </div>
      <el-table :data="filtered" border>
        <el-table-column prop="username" label="用户名" />
        <el-table-column prop="role" label="角色" width="120" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该用户？" @confirm="remove(row.id)">
              <template #reference>
                <el-button size="small" type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <el-dialog v-model="visible" :title="form.id ? '编辑用户' : '新增用户'">
        <el-form :model="form" label-width="80px">
          <el-form-item label="用户名">
            <el-input v-model="form.username" />
          </el-form-item>
          <el-form-item label="密码" v-if="!form.id">
            <el-input v-model="form.password" type="password" />
          </el-form-item>
          <el-form-item label="角色">
            <el-select v-model="form.role">
              <el-option label="普通用户" value="user" />
              <el-option label="管理员" value="admin" />
            </el-select>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="visible=false">取消</el-button>
          <el-button type="primary" @click="save">保存</el-button>
        </template>
      </el-dialog>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { listUsers, createUser, updateUser, deleteUser } from '@/services/users'

const users = ref<{ id: number; username: string; role: 'user' | 'admin' }[]>([])
const keyword = ref('')
const filtered = computed(() => users.value.filter(u => u.username.includes(keyword.value)))

const visible = ref(false)
const form = reactive<{ id?: number; username: string; password?: string; role: 'user' | 'admin' }>({ username: '', role: 'user' })

onMounted(async () => {
  users.value = await listUsers()
})

function openCreate() {
  Object.assign(form, { id: undefined, username: '', password: '', role: 'user' as const })
  visible.value = true
}

function openEdit(row: any) {
  Object.assign(form, { id: row.id as number, username: row.username, role: row.role })
  visible.value = true
}

async function save() {
  if (!form.id) {
    const created = await createUser({ username: form.username, password: form.password!, role: form.role })
    users.value.push(created)
  } else {
    const updated = await updateUser({ id: form.id, username: form.username, role: form.role })
    const idx = users.value.findIndex(u => u.id === updated.id)
    if (idx >= 0) users.value[idx] = updated
  }
  visible.value = false
}

async function remove(id: number) {
  await deleteUser(id)
  users.value = users.value.filter(u => u.id !== id)
}
</script>

<style scoped>
.wrap { padding: 12px; }
.toolbar { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
</style>
