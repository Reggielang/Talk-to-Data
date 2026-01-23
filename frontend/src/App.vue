<template>
  <div id="app" class="app-container">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '@/stores'

const chatStore = useChatStore()

onMounted(() => {
  // 如果没有会话，创建一个默认会话
  if (chatStore.allSessions.length === 0) {
    chatStore.createSession('新对话')
  }
})
</script>

<style scoped lang="scss">
.app-container {
  height: 100%;
  width: 100%;
}
</style>
