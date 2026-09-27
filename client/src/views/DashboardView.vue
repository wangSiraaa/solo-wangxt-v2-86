<template>
  <div>
    <div class="card">
      <h3>
        合同总览
        <span class="muted" v-if="data.as_of">（截至 {{ data.as_of }} 末的时点快照）</span>
        <span class="muted" v-else>（全部已发生业务口径）</span>
      </h3>
      <div class="form-row" style="margin: 0 0 12px">
        <label class="muted">查看截至期间：</label>
        <select v-model="asOf" @change="load">
          <option value="">全部</option>
          <option v-for="p in data.periods" :key="p" :value="p">{{ p }}</option>
        </select>
        <span class="muted">递延余额 = 累计收款 − 累计确认（正数为合同负债，负数为已履约未收足款）</span>
      </div>
      <div class="cards">
        <div v-for="c in data.contracts" :key="c.contract_id" class="contract-card">
          <div class="cc-head">
            <router-link :to="`/contracts/${c.contract_id}`" class="cc-num">{{ c.number }}</router-link>
            <span class="cc-customer">{{ c.customer }}</span>
          </div>
          <div class="cc-grid">
            <div class="cc-item">
              <div class="cc-label">合同金额</div>
              <div class="cc-value num">{{ fmt(c.total_price) }}</div>
            </div>
            <div class="cc-item">
              <div class="cc-label">累计收款</div>
              <div class="cc-value num">{{ fmt(c.received_total) }}</div>
            </div>
            <div class="cc-item">
              <div class="cc-label">已确认收入</div>
              <div class="cc-value num ok-text">{{ fmt(c.recognized_total) }}</div>
            </div>
            <div class="cc-item">
              <div class="cc-label">递延余额</div>
              <div class="cc-value num" :class="Number(c.deferred_balance) >= 0 ? 'warn-text' : 'neg-text'">
                {{ fmt(c.deferred_balance) }}
              </div>
            </div>
            <div class="cc-item">
              <div class="cc-label">剩余履约义务</div>
              <div class="cc-value num">{{ fmt(c.remaining_obligation) }}</div>
            </div>
          </div>
          <div class="cc-bar" :title="`确认进度 ${pct(c)}%`">
            <div class="cc-bar-fill" :style="{ width: pct(c) + '%' }"></div>
          </div>
          <div class="muted" style="margin-top:4px">确认进度 {{ pct(c) }}%（已确认 / 分摊总额）</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3>逐期确认矩阵（期间 × 合同）</h3>
      <table>
        <thead>
          <tr>
            <th>合同</th>
            <th v-for="p in data.periods" :key="p">{{ p }}</th>
            <th>累计已确认</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in data.contracts" :key="c.contract_id">
            <td>
              <router-link :to="`/contracts/${c.contract_id}`">{{ c.number }}</router-link>
              <span class="muted"> {{ c.customer }}</span>
            </td>
            <td v-for="p in data.periods" :key="p" class="num">
              <span v-if="Number(c.recognized_by_period[p])">{{ fmt(c.recognized_by_period[p]) }}</span>
              <span v-else-if="Number(c.planned_by_period[p])" class="badge plan">
                待 {{ fmt(c.planned_by_period[p]) }}
              </span>
              <span v-else class="muted">—</span>
            </td>
            <td class="num"><strong>{{ fmt(c.recognized_total) }}</strong></td>
          </tr>
        </tbody>
      </table>
      <div class="muted" style="margin-top:8px">
        蓝色「待」= 已生成确认计划但尚未到确认动作（订阅期待确认）；空白 = 该期间无计划。
        实施类未验收、按量类未录用量时不产生任何计划——不计入收入。
      </div>
    </div>
    <div v-if="error" class="error-box">{{ error }}</div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, fmt } from '../api'

const data = reactive({ periods: [], contracts: [], as_of: null })
const asOf = ref('')
const error = ref('')

function pct(c) {
  const total = Number(c.allocated_total)
  if (!total) return 0
  return Math.min(100, Math.round((Number(c.recognized_total) / total) * 100))
}

async function load() {
  error.value = ''
  try {
    Object.assign(data, await api.summary(asOf.value || undefined))
  } catch (e) {
    error.value = `加载失败：${e.message}`
  }
}

onMounted(load)
</script>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }
.contract-card { border: 1px solid #e5e9f0; border-radius: 10px; padding: 14px 16px; background: #fbfcfe; }
.cc-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.cc-num { font-weight: 700; color: #0f4c81; }
.cc-customer { color: #4b5563; font-size: 13px; }
.cc-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
.cc-label { font-size: 11.5px; color: #8a94a3; }
.cc-value { font-size: 15px; font-weight: 600; margin-top: 2px; }
.ok-text { color: #177245; }
.warn-text { color: #b35c00; }
.neg-text { color: #b3352b; }
.cc-bar { height: 6px; background: #e8edf3; border-radius: 999px; margin-top: 10px; overflow: hidden; }
.cc-bar-fill { height: 100%; background: linear-gradient(90deg, #2b7cd3, #177245); }
a { color: #0f4c81; }
</style>
