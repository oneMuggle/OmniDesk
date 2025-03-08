import { createRouter, createWebHistory } from 'vue-router';
import Login from '../components/Login.vue';
import MainPage from '../components/MainPage.vue';
import CalendarPage from '../components/CalendarPage.vue';
import HelloWorld from '../components/HelloWorld.vue';
import Home from '../components/Home.vue';

const routes = [
  { path: '/', component: Home, name: 'Home' },
  { path: '/helloworld', component: HelloWorld, name: 'HelloWorld' },
  { path: '/main', component: MainPage, name: 'Main' },
  { path: '/login', component: Login, name: 'Login' },
  { 
    path: '/calendar', 
    component: CalendarPage, 
    name: 'Calendar',
    props: (route: any) => ({ query: route.query })
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
