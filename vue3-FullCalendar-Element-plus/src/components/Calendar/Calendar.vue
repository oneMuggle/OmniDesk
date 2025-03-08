<template>
  <div class="calender-container">
    <el-card>
      <!-- 自定义头部，切换视图类型和切换日期 -->
      <div class="calender-header mb2">
        <div class="header-left">
          <span class="time-title">{{ currentDate }}</span>
          <el-button
            :icon="ArrowLeftBold"
            circle
            @click="
              Tcalendar.prev();
              dayTime();
            "
          />
          <el-button
            :icon="ArrowRightBold"
            circle
            @click="
              Tcalendar.next();
              dayTime();
            "
          />
        </div>
        <div class="header-right">
          <el-button
            class="btn-m2"
            type="primary"
            @click="
              Tcalendar.today();
              dayTime();
            "
            plain
            round
            >今天</el-button
          >
          <el-select
            v-model="type"
            placeholder="视图类型"
            style="width: 80px"
            @change="changeType"
          >
            <el-option label="月" value="dayGridMonth" />
            <el-option label="周" value="timeGridWeek" />
            <el-option label="天" value="timeGridDay" />
            <el-option label="列" value="listWeek" />
          </el-select>
          <!-- 选择月份的日期框 -->
          <el-date-picker
            v-if="type === 'dayGridMonth'"
            v-model="showMonth"
            type="month"
            :clearable="false"
            placeholder="请选择日期"
            style="margin-left: 10px; vertical-align: middle"
            @change="changeDate"
          />
          <el-button class="ml2" type="primary" :icon="Plus" plain @click="drawerVisile = true"
            >新增排班</el-button
          >
        </div>
      </div>
      <div ref="fullcalendar" class="card"></div>
    </el-card>
    <drawerAddPlan v-model:drawerVisile="drawerVisile" />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onMounted, onUnmounted } from "vue";
import drawerAddPlan from "../drawerAddPlan.vue";
const emit = defineEmits(['eventClick', 'selectDate', 'eventResize', 'eventDrop']);
const drawerVisile = ref(false);
import { Calendar } from "@fullcalendar/core";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import listPlugin from "@fullcalendar/list";
import interactionPlugin from "@fullcalendar/interaction";
import dayjs from "dayjs";
import { ArrowLeftBold, ArrowRightBold, Plus } from "@element-plus/icons-vue";

const state = {
  infoList: ref([]),
  Tcalendar: ref(),
};

const fetchEvents = async () => {
  try {
    const response = await fetch('/api/events');
    const events = await response.json();
    state.infoList.value = events;
    if (Tcalendar.value) {
      Tcalendar.value.removeAllEvents();
      Tcalendar.value.addEventSource(events);
    }
  } catch (error) {
    console.error('Failed to fetch events:', error);
  }
};

const fullcalendar = ref();
const Tcalendar = ref();
const type = ref("dayGridMonth"); // 默认月视图
const currentDate = ref(); // 当前时间
const showMonth = ref(dayjs().format("YYYY-MM")); // 默认当前月份

const initCalendar = () => {
  Tcalendar.value = new Calendar(fullcalendar.value, {
    plugins: [dayGridPlugin, timeGridPlugin, listPlugin, interactionPlugin],
    initialView: type.value,
    aspectRatio: 1.8,
    locale: "zh-cn",
    handleWindowResize: true,
    editable: true,
    droppable: true,
    eventDurationEditable: true,
    eventResizableFromStart: true,
    selectable: true,
    firstDay: 1,
    unselectAuto: true,
    dayMaxEvents: true,
    headerToolbar: false,
    allDayText: "全天",
    nowIndicator: true,
    eventMaxStack: 2,
    events: state.infoList.value,
    eventClassNames: function (arg) {
      return [arg.event.extendedProps.class];
    },
    eventContent: function (arg) {
      const italicEl = document.createElement("div");
      if (type.value === "listWeek") {
        const nameEl = document.createElement("h4");
        nameEl.setAttribute("class", `h4`);
        nameEl.innerHTML = arg.event.extendedProps.name;
        italicEl.append(nameEl);
        const text1El = document.createElement("p");
        text1El.innerHTML = arg.event.extendedProps.job;
        italicEl.append(text1El);
        const text2El = document.createElement("p");
        text2El.innerHTML = "描述：" + arg.event.extendedProps.description;
        italicEl.append(text2El);
      } else {
        const titleEl = document.createElement("div");
        titleEl.setAttribute("class", `calendar-title`);
        const nameEl = document.createElement("span");
        nameEl.innerHTML = arg.event.extendedProps.name;
        titleEl.append(nameEl);
        const timeEl = document.createElement("span");
        if (arg.event.start && arg.event.end) {
          timeEl.innerHTML =
            dayjs(arg.event.start).format("HH:mm") +
            "-" +
            dayjs(arg.event.end).format("HH:mm");
          if (timeEl.innerHTML !== "00:00-00:00") {
            titleEl.append(timeEl);
          }
        }
        italicEl.append(titleEl);
      }
      italicEl.setAttribute("class", `calendar-card`);
      return { domNodes: [italicEl] };
    },
    noEventsContent: function () {
      const noEl = document.createElement("div");
      noEl.innerHTML = "暂无日程安排，请安排相关日程";
      return { domNodes: [noEl] };
    },
    eventClick: function (info) {
      emit('eventClick', info);
    },
    select: function (info) {
      emit('selectDate', info);
      drawerVisile.value = true;
    },
    eventResize: function (info) {
      emit('eventResize', info);
    },
    eventDrop: function (info) {
      emit('eventDrop', info);
    },
  });
  Tcalendar.value.render();
};

const changeType = (type: any) => {
  Tcalendar.value.changeView(type);
  dayTime();
};

const dayTime = () => {
  if (type.value === "dayGridMonth") {
    currentDate.value = dayjs(Tcalendar.value.getDate()).format("YYYY年MM月");
  } else if (type.value === "timeGridWeek" || type.value === "listWeek") {
    currentDate.value =
      dayjs(Tcalendar.value.getDate()).format("YYYY年MM月DD日") +
      " - " +
      dayjs(Tcalendar.value.getDate()).add(6, "day").format("DD日");
  } else if (type.value === "timeGridDay") {
    currentDate.value = dayjs(Tcalendar.value.getDate()).format(
      "YYYY年MM月DD日"
    );
  }
};

const changeDate = (date: any) => {
  Tcalendar.value.gotoDate(dayjs(date).format("YYYY-MM"));
  currentDate.value = dayjs(date).format("YYYY年MM月");
};

onMounted(() => {
  nextTick(() => {
    initCalendar();
    dayTime();
    fetchEvents();
  });
});

onUnmounted(() => {
  if (Tcalendar.value) {
    Tcalendar.value.destroy();
  }
});
</script>

<style lang="scss" scoped>
.calender-container {
  width: 100%;
  max-width: 1525px;
  margin: 0 auto;
  padding: 20px;
  box-sizing: border-box;
  
  .card {
    height: 600px;
  }
}

.calender-header {
  display: flex;
  justify-content: space-between;
  .header-left,
  .header-right {
    display: flex;
    align-items: center;
    .time-title {
      font-weight: bold;
      margin-right: 20px;
    }
  }
  .header-left {
    h1 {
      margin-right: 20px;
    }
  }
}

.btn-m2 {
  margin-right: 20px;
}
.ml2 {
  margin-left: 20px !important;
}
.mb2 {
  margin-bottom: 20px !important;
}
</style>
