<template>
  <el-header>
    <div class="nav-container">
      <div class="nav-left">
        <el-button type="text" @click="goHome">Home</el-button>
      </div>
      <div class="nav-right">
        <el-button v-if="!isAuthenticated" type="primary" @click="goLogin">Login</el-button>
        <el-button v-else type="danger" @click="logout">Logout</el-button>
      </div>
    </div>
  </el-header>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const isAuthenticated = computed(() => !!authStore.accessToken)

const goHome = () => {
  router.push('/')
}

const goLogin = () => {
  router.push('/login')
}

const logout = () => {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.nav-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.nav-left {
  display: flex;
  align-items: center;
}

.nav-right {
  display: flex;
  align-items: center;
}
</style>
