<template>
  <div>
    <!-- 日历组件代码 -->
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../../utils/api'

const events = ref([])

const fetchEvents = async () => {
  const { data } = await api.get('/api/events/')
  events.value = data
}

onMounted(fetchEvents)
</script>
