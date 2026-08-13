import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tasks' },
    { path: '/tasks', component: () => import('@/views/TaskListView.vue') },
    { path: '/tasks/new', component: () => import('@/views/TaskCreateView.vue') },
    { path: '/tasks/:id', component: () => import('@/views/TaskDetailView.vue') },
    { path: '/settings', component: () => import('@/views/SettingsView.vue') },
    { path: '/:pathMatch(.*)*', component: () => import('@/views/NotFoundView.vue') }
  ]
})
export default router
