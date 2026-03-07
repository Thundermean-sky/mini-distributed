import { createRouter, createWebHistory } from 'vue-router'
import Overview from '../views/Overview.vue'   // 我们后面会创建

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('../views/Overview.vue')
    },
    {
      path: '/workers',
      name: 'workers',
      component: () => import('../views/Workers.vue')
    },
    {
      path: '/tasks',
      name: 'tasks',
      component: () => import('../views/Tasks.vue')
    }
  ]
})

export default router