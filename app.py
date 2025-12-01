<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <title>Color Powder 系統</title>

  <!-- Element Plus + Vue -->
  <link rel="stylesheet" href="https://unpkg.com/element-plus/dist/index.css">
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <script src="https://unpkg.com/element-plus/dist/index.full.js"></script>
  <script src="https://unpkg.com/@element-plus/icons-vue/dist/index.iife.min.js"></script>

  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { margin: 0; font-family: Arial, sans-serif; }
    #app { display: flex; height: 100vh; overflow: hidden; }
    .menu {
      width: 240px;
      background: #1f2d3d;
      color: white;
      transition: width .3s;
      flex-shrink: 0;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
    }
    .menu.collapsed { width: 70px; }
    iframe { flex: 1; border: none; height: 100vh; width: 100%; }

    .menu-header {
      height: 60px;
      display: flex;
      align-items: center;
      padding-left: 16px;
      font-size: 20px;
      color: #fff;
      border-bottom: 1px solid #3a4750;
      position: relative;
      flex-shrink: 0;
    }
    .collapse-btn { position: absolute; right: 10px; top: 15px; cursor: pointer; color: #fff; }
    .el-menu { 
      border-right: none; 
      flex: 1;
      overflow-y: auto;
    }
    .el-menu-item, .el-sub-menu__title { 
      font-size: 14px;
      height: 50px;
      line-height: 50px;
    }
    .el-sub-menu .el-menu-item {
      min-width: auto;
      padding-left: 45px !important;
    }
  </style>
</head>

<body>
<div id="app">
  <!-- 左側選單 -->
  <div :class="['menu', isCollapse ? 'collapsed' : '']">
    <div class="menu-header">
      <span v-if="!isCollapse">📘 Color 系統</span>
      <span class="collapse-btn" @click="isCollapse = !isCollapse">
        <el-icon><ArrowLeftBold v-if="!isCollapse" /><ArrowRightBold v-else /></el-icon>
      </span>
    </div>

    <el-menu
      :collapse="isCollapse"
      background-color="#1f2d3d"
      text-color="#fff"
      active-text-color="#ffd04b"
      @select="handleSelect"
    >
      <!-- 色粉管理 -->
      <el-sub-menu index="1">
        <template #title>
          <el-icon><Brush /></el-icon>
          <span>色粉管理</span>
        </template>
        <el-menu-item index="1-1">色粉管理</el-menu-item>
      </el-sub-menu>

      <!-- 配方管理 -->
      <el-sub-menu index="2">
        <template #title>
          <el-icon><Folder /></el-icon>
          <span>配方管理</span>
        </template>
        <el-menu-item index="2-1">客戶名單</el-menu-item>
        <el-menu-item index="2-2">配方管理</el-menu-item>
      </el-sub-menu>

      <!-- 生產管理 -->
      <el-sub-menu index="3">
        <template #title>
          <el-icon><Document /></el-icon>
          <span>生產管理</span>
        </template>
        <el-menu-item index="3-1">生產單</el-menu-item>
        <el-menu-item index="3-2">代工排程</el-menu-item>
      </el-sub-menu>

      <!-- 庫存管理 -->
      <el-sub-menu index="4">
        <template #title>
          <el-icon><Box /></el-icon>
          <span>庫存管理</span>
        </template>
        <el-menu-item index="4-1">庫存區</el-menu-item>
      </el-sub-menu>

      <!-- 查詢區 -->
      <el-sub-menu index="5">
        <template #title>
          <el-icon><Search /></el-icon>
          <span>查詢區</span>
        </template>
        <el-menu-item index="5-1">Pantone 色號表</el-menu-item>
        <el-menu-item index="5-2">交叉查詢區</el-menu-item>
      </el-sub-menu>

      <!-- 備份區 -->
      <el-sub-menu index="6">
        <template #title>
          <el-icon><Document /></el-icon>
          <span>備份區</span>
        </template>
        <el-menu-item index="6-1">匯入備份</el-menu-item>
      </el-sub-menu>

    </el-menu>
  </div>

  <!-- 右側內容 iframe -->
  <iframe id="appFrame" :src="iframeUrl"></iframe>
</div>

<script>
const { createApp, ref } = Vue;
const { Brush, Folder, Document, Box, Search, ArrowLeftBold, ArrowRightBold } = ElementPlusIconsVue;

createApp({
  components: { Brush, Folder, Document, Box, Search, ArrowLeftBold, ArrowRightBold },

  setup() {
    const iframeUrl = ref("https://color-powder-app.streamlit.app/#recipe-create");
    const isCollapse = ref(false);

    const handleSelect = (index) => {
      let tabHash = "";
      switch(index){
        case "1-1": tabHash = "#color-powder"; break;
        case "2-1": tabHash = "#customer"; break;
        case "2-2": tabHash = "#recipe-create"; break;
        case "3-1": tabHash = "#production-order"; break;
        case "3-2": tabHash = "#outsourcing"; break;
        case "4-1": tabHash = "#inventory"; break;
        case "5-1": tabHash = "#pantone-table"; break;
        case "5-2": tabHash = "#cross-query"; break;
        case "6-1": tabHash = "#backup"; break;
      }
      // 直接更新 iframe 的 URL
      iframeUrl.value = `https://color-powder-app.streamlit.app/${tabHash}`;
    };

    return { iframeUrl, handleSelect, isCollapse };
  }
}).mount("#app");
</script>
</body>
</html>
