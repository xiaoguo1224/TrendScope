import { defineStore } from 'pinia'
import { listResearchTasks } from '@/api/research'
import type { ResearchTask } from '@/types'

export const useTaskStore = defineStore('tasks', {
  state: () => ({ tasks: [] as ResearchTask[], loading: false }),
  actions: { async fetchTasks() { this.loading = true; try { this.tasks = await listResearchTasks() } finally { this.loading = false } } }
})
