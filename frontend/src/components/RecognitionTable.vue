<script setup>
import { ref, watch } from "vue";
import { api } from "../api.js";

const props = defineProps({ asOf: String });

const rows = ref([]);
const loadedAsOf = ref("");
const statusFilter = ref("all");
const typeFilter = ref("all");

const typeLabel = {
  subscription: "账号订阅",
  implementation: "一次性实施",
  usage: "按量服务",
};

async function load() {
  const data = await api.getRecognition(props.asOf);
  rows.value = data.results;
  loadedAsOf.value = data.as_of;
}

watch(() => props.asOf, load, { immediate: true });

function filtered() {
  return rows.value.filter(
    (r) =>
      (statusFilter.value === "all" || r.status === statusFilter.value) &&
      (typeFilter.value === "all" || r.obligation_type === typeFilter.value)
  );
}
</script>

<template>
  <div class="section">
    <h3>
      全部合同项的收入确认计划（截至 {{ loadedAsOf }}）
    </h3>
    <div class="toolbar">
      <label>类型：
        <select v-model="typeFilter">
          <option value="all">全部</option>
          <option value="subscription">账号订阅</option>
          <option value="implementation">一次性实施</option>
          <option value="usage">按量服务</option>
        </select>
      </label>
      <label>状态：
        <select v-model="statusFilter">
          <option value="all">全部</option>
          <option value="recognized">已确认</option>
          <option value="pending">待确认</option>
        </select>
      </label>
    </div>
    <table>
      <thead>
        <tr>
          <th>合同</th>
          <th>客户</th>
          <th>合同项</th>
          <th>类型</th>
          <th>确认期间</th>
          <th class="num">金额</th>
          <th>状态</th>
          <th>确认依据</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in filtered()" :key="r.id">
          <td>{{ r.contract_number }}</td>
          <td>{{ r.customer }}</td>
          <td>{{ r.obligation_code }} {{ r.obligation_name }}</td>
          <td><span class="tag" :class="r.obligation_type">{{ typeLabel[r.obligation_type] }}</span></td>
          <td>
            <template v-if="r.period_end">{{ r.period_start || '—' }} ~ {{ r.period_end }}</template>
            <template v-else class="muted">条件未满足</template>
          </td>
          <td class="num">{{ r.amount }}</td>
          <td>
            <span class="tag" :class="r.status">
              {{ r.status === "recognized" ? "已确认" : "待确认" }}
            </span>
          </td>
          <td class="basis">{{ r.basis }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
