<template>
  <div class="home-container">
    <NavBar />
    <h1>Welcome to the Home Page</h1>
    <HelloWorld msg="Vue 3 + TypeScript + Vite" />
  </div>
</template>

<script setup>
import NavBar from './NavBar.vue'
import HelloWorld from './HelloWorld.vue'
</script>

<style scoped>
h1 {
  text-align: center;
  margin-top: 20px;
}
</style>
