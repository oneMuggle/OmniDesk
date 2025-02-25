import { createRouter, createWebHistory } from 'vue-router';
import Login from '../components/Login.vue';
import CalendarView from '../components/CalendarView.vue';

const routes = [
  { path: '/login', component: Login },
  { path: '/calendar', component: CalendarView },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
