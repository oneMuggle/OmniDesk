import { createApp } from 'vue'
import './style.scss'
import App from './App.vue'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'element-plus/dist/index.css'
import { createPinia } from 'pinia'
import router from './router'

const app = createApp(App)

app.use(ElementPlus, { locale: zhCn })
app.use(createPinia())
app.use(router)

app.mount('#app')
