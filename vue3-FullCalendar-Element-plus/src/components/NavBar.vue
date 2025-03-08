<template>
  <el-menu
    mode="horizontal"
    :default-active="route.path"
    router
    background-color="#545c64"
    text-color="#fff"
    active-text-color="#ffd04b"
  >
    <el-menu-item index="/">Home</el-menu-item>
    <el-menu-item index="/main">Main</el-menu-item>
    <el-menu-item index="/calendar">Calendar</el-menu-item>
    <el-menu-item index="/login" style="float: right">Login</el-menu-item>
  </el-menu>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>


<style scoped>
.el-menu {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1000;
}
</style>
