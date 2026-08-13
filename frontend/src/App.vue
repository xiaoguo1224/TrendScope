<script setup lang="ts">
import { DataAnalysis, DocumentAdd, List, Setting } from '@element-plus/icons-vue'
</script>

<template>
  <el-container class="shell">
    <el-aside width="232px" class="aside">
      <div class="brand"><el-icon><DataAnalysis /></el-icon> TrendScope</div>
      <el-menu router :default-active="$route.path" class="menu">
        <el-menu-item index="/tasks"><el-icon><List /></el-icon><span>研究任务</span></el-menu-item>
        <el-menu-item index="/tasks/new"><el-icon><DocumentAdd /></el-icon><span>创建研究</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>系统配置</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container><el-main><router-view /></el-main></el-container>
  </el-container>
</template>
