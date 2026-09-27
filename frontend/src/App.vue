<script setup>
import { computed, onMounted, ref } from "vue";
import { api } from "./api.js";
import SummaryDashboard from "./components/SummaryDashboard.vue";
import ContractDetail from "./components/ContractDetail.vue";
import RecognitionTable from "./components/RecognitionTable.vue";

const today = new Date();
const isoToday = today.toISOString().slice(0, 10);

const asOf = ref(isoToday);
const view = ref("summary"); // summary | contract | recognition
const contracts = ref([]);
const currentId = ref(null);
const contractData = ref(null);
const summaryData = ref(null);
const error = ref("");
const loading = ref(false);

const views = [
  { key: "summary", label: "合同·收款·收入 总览" },
  { key: "recognition", label: "全部确认计划" },
];

const currentContract = computed(() =>
  contracts.value.find((c) => c.id === currentId.value)
);

async function loadContracts() {
  contracts.value = await api.listContracts();
}

async function loadSummary() {
  loading.value = true;
  error.value = "";
  try {
    summaryData.value = await api.getSummary(asOf.value);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function openContract(id) {
  currentId.value = id;
  view.value = "contract";
  await reloadContract();
}

async function reloadContract() {
  if (!currentId.value) return;
  loading.value = true;
  error.value = "";
  try {
    contractData.value = await api.getContract(currentId.value, asOf.value);
  } catch (e) {
    error.value = e.message;
  } finally {
    loading.value = false;
  }
}

async function onAsOfChange() {
  if (view.value === "summary") await loadSummary();
  else if (view.value === "contract") await reloadContract();
  else if (view.value === "recognition") view.value = "recognition";
}

const recognitionKey = ref(0);
async function goRecognition() {
  view.value = "recognition";
  recognitionKey.value++;
}

onMounted(async () => {
  await loadContracts();
  await loadSummary();
});
</script>

<template>
  <header class="app-header">
    <h1>收入确认核算应用 · 账号订阅 / 一次性实施 / 按量服务</h1>
    <p>
      示例政策仅用于本项目，不宣称覆盖任何会计准则 ·
      开票与收款不直接作为收入，收入按履约进度（订阅逐月、实施凭验收、按量凭用量）确认
    </p>
  </header>

  <div class="layout">
    <aside class="sidebar">
      <h2>合同</h2>
      <div
        v-for="c in contracts"
        :key="c.id"
        class="contract-item"
        :class="{ active: view === 'contract' && currentId === c.id }"
        @click="openContract(c.id)"
      >
        <div class="num">{{ c.number }}</div>
        <div class="cust">{{ c.customer }}</div>
      </div>
      <h2 style="margin-top: 20px">报表</h2>
      <div
        v-for="v in views"
        :key="v.key"
        class="contract-item"
        :class="{ active: view === v.key }"
        @click="v.key === 'summary' ? (view = 'summary', loadSummary()) : goRecognition()"
      >
        <div class="num">{{ v.label }}</div>
      </div>
    </aside>

    <main class="main">
      <div class="toolbar">
        <label><strong>核算截止日：</strong></label>
        <input type="date" v-model="asOf" @change="onAsOfChange" />
        <button class="btn ghost" @click="asOf = isoToday; onAsOfChange()">回到今天</button>
        <span v-if="loading" class="muted">加载中…</span>
        <span v-if="error" class="error">{{ error }}</span>
      </div>

      <div class="note-banner">
        三账口径：<b>签约金额</b>是合同组成；<b>收款金额</b>是现金口径；
        <b>已确认收入</b>是当期真正履约的部分。
        递延余额（现金）= 收款 − 已确认收入；合同负债 = 合同对价 − 已确认收入。
        开票金额仅作核对，<b>开票不等于收入</b>。
      </div>

      <SummaryDashboard
        v-if="view === 'summary'"
        :data="summaryData"
        :as-of="asOf"
        @open="openContract"
      />

      <ContractDetail
        v-else-if="view === 'contract' && contractData"
        :data="contractData"
        :as-of="asOf"
        @changed="reloadContract"
      />

      <RecognitionTable
        v-else-if="view === 'recognition'"
        :key="recognitionKey"
        :as-of="asOf"
      />
    </main>
  </div>
</template>
