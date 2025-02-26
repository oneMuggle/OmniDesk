import { createRouter, createWebHistory } from 'vue-router';
import Login from '../components/Login.vue';
import CalendarView from '../components/CalendarView.vue';
import MainPage from '../components/MainPage.vue';
import CalendarPage from '../components/CalendarPage.vue';
import HelloWorld from '../components/HelloWorld.vue';

const routes = [
  { path: '/', component: HelloWorld, name: 'Home' },
  { path: '/main', component: MainPage, name: 'Main' },
  { path: '/login', component: Login },
  { path: '/calendar', component: CalendarPage },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
