import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import DashboardView from './views/DashboardView.vue'
import ContractDetailView from './views/ContractDetailView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/contracts/:id', name: 'contract', component: ContractDetailView, props: true },
  ],
})

createApp(App).use(router).mount('#app')
