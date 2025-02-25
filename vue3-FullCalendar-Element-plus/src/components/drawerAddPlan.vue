<template>
  <div class="container">
    <el-drawer
      :model-value="drawerVisile"
      :before-close="handleClose"
      :close-on-click-modal="false"
      title="新增排班"
    >
      <el-form :model="form" ref="formRef" label-width="80px">
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="请输入标题"></el-input>
        </el-form-item>
        <el-form-item label="执行人" prop="executor">
          <el-input v-model="form.executor" placeholder="请输入执行人"></el-input>
        </el-form-item>
        <el-form-item label="岗位" prop="job">
          <el-select v-model="form.job" placeholder="请选择岗位">
            <el-option label="产线员工" value="产线员工"></el-option>
            <el-option label="负责人" value="负责人"></el-option>
            <el-option label="员工" value="员工"></el-option>
            <el-option label="生产员工1" value="生产员工1"></el-option>
            <el-option label="生产员工2" value="生产员工2"></el-option>
            <el-option label="生产员工3" value="生产员工3"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="执行时间" prop="time">
          <el-date-picker
            v-model="form.time"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            :default-time="['00:00:00', '23:59:59']"
          ></el-date-picker>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            type="textarea"
            v-model="form.description"
            placeholder="请输入描述"
          ></el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSubmit">提交</el-button>
          <el-button @click="handleClose">取消</el-button>
        </el-form-item>
      </el-form>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";

const props = defineProps(["drawerVisile"]);
const emits = defineEmits(["update:drawerVisile"]);

const formRef = ref();
const form = reactive({
  title: "",
  executor: "",
  job: "",
  time: [],
  description: "",
});

/**
 * 关闭抽屉
 */
const handleClose = () => {
  emits("update:drawerVisile", false);
  console.log("close");
};

/**
 * 提交表单
 */
const handleSubmit = () => {
  formRef.value.validate((valid: boolean) => {
    if (valid) {
      console.log("提交成功", form);
      handleClose();
    } else {
      console.log("提交失败");
      return false;
    }
  });
};
</script>

<style scoped>
.container {
  padding: 20px;
}
</style>
