<template>
  <div v-if="contract">
    <div class="card">
      <h3>
        {{ contract.number }} · {{ contract.customer }}
        <span class="muted">签订于 {{ contract.signed_on }}</span>
      </h3>
      <div class="headline">
        <div class="hl-item">
          <div class="hl-label">合同金额（交易价格）</div>
          <div class="hl-value num">{{ fmt(contract.total_price) }}</div>
        </div>
        <div class="hl-item">
          <div class="hl-label">累计收款</div>
          <div class="hl-value num">{{ fmt(contract.totals.received_total) }}</div>
        </div>
        <div class="hl-item">
          <div class="hl-label">已确认收入</div>
          <div class="hl-value num ok-text">{{ fmt(contract.totals.recognized_total) }}</div>
        </div>
        <div class="hl-item">
          <div class="hl-label">递延余额（收款−确认）</div>
          <div class="hl-value num warn-text">{{ fmt(contract.totals.deferred_balance) }}</div>
        </div>
        <div class="hl-item">
          <div class="hl-label">剩余履约义务</div>
          <div class="hl-value num">{{ fmt(contract.totals.remaining_obligation) }}</div>
        </div>
      </div>
      <div class="muted" v-if="contract.note">{{ contract.note }}</div>
    </div>

    <div class="card">
      <h3>合同组成 · 履约义务与交易价格分摊（相对独立售价法）</h3>
      <table>
        <thead>
          <tr>
            <th>#</th><th>履约义务</th><th>类型</th>
            <th>独立售价 SSP</th><th>分摊后交易价格</th>
            <th>已确认</th><th>待确认</th><th>履约要素</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="line in contract.lines" :key="line.id">
            <td>{{ line.sort }}</td>
            <td>{{ line.name }}</td>
            <td><span class="badge plan">{{ line.line_type_display }}</span></td>
            <td class="num">{{ fmt(line.ssp) }}</td>
            <td class="num"><strong>{{ fmt(line.allocated_price) }}</strong></td>
            <td class="num ok-text">{{ fmt(line.recognized_amount) }}</td>
            <td class="num" :class="Number(line.pending_amount) > 0 ? 'warn-text' : ''">
              {{ fmt(line.pending_amount) }}
            </td>
            <td class="muted" style="text-align:left; font-size:12px">
              <template v-if="line.line_type === 'SUBSCRIPTION'">
                {{ line.service_start }} ~ {{ line.service_end }}，按月直线确认
              </template>
              <template v-else-if="line.line_type === 'IMPLEMENTATION'">
                <span v-if="line.acceptance" class="badge ok">
                  已验收 {{ line.acceptance.accepted_on }}（{{ line.acceptance.reference }}）
                </span>
                <span v-else class="badge wait">未验收 · 保持待确认</span>
              </template>
              <template v-else>
                预估 {{ fmt(line.estimated_units) }} {{ line.unit_label }}，
                分摊单价 {{ line.usage_unit_price }} / {{ line.unit_label }}
              </template>
            </td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <td colspan="3"><strong>合计</strong></td>
            <td class="num"><strong>{{ fmt(sumSsp) }}</strong></td>
            <td class="num"><strong>{{ fmt(contract.totals.allocated_total) }}</strong></td>
            <td class="num"><strong>{{ fmt(contract.totals.recognized_total) }}</strong></td>
            <td class="num"><strong>{{ fmt(contract.totals.remaining_obligation) }}</strong></td>
            <td></td>
          </tr>
        </tfoot>
      </table>
    </div>

    <div class="card">
      <h3>确认计划与确认依据（可追到对应合同项）</h3>
      <table>
        <thead>
          <tr>
            <th>合同项</th><th>期间</th><th>金额</th><th>状态</th><th>确认依据</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <template v-for="line in contract.lines" :key="line.id">
            <tr v-for="entry in line.schedule" :key="entry.id">
              <td>
                <span class="muted">#{{ line.sort }}</span> {{ line.name }}
              </td>
              <td>{{ entry.period }}</td>
              <td class="num">{{ fmt(entry.amount) }}</td>
              <td>
                <span class="badge" :class="entry.status === 'RECOGNIZED' ? 'ok' : 'plan'">
                  {{ entry.status_display }}
                </span>
              </td>
              <td class="muted" style="text-align:left; font-size:12px">
                {{ entry.basis_type_display }}<br />{{ entry.basis_note }}
              </td>
              <td>
                <button
                  v-if="entry.status === 'PLANNED'"
                  class="ghost"
                  :disabled="busy"
                  @click="recognize(entry.period)"
                >确认 {{ entry.period }}</button>
                <span v-else class="muted">—</span>
              </td>
            </tr>
            <tr v-if="line.line_type === 'IMPLEMENTATION' && !line.acceptance">
              <td><span class="muted">#{{ line.sort }}</span> {{ line.name }}</td>
              <td colspan="5" class="muted" style="text-align:left">
                尚无验收证据 → 不生成确认计划，分摊价 {{ fmt(line.allocated_price) }} 保持待确认
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>递延余额对照（收款 ≠ 收入）</h3>
      <table>
        <thead>
          <tr><th>口径</th><th>金额</th><th>说明</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>累计收款</td>
            <td class="num">{{ fmt(contract.totals.received_total) }}</td>
            <td class="muted" style="text-align:left">实际收到的合同款（开票/收款不确认收入）</td>
          </tr>
          <tr>
            <td>减：累计已确认收入</td>
            <td class="num">{{ fmt(contract.totals.recognized_total) }}</td>
            <td class="muted" style="text-align:left">已履约部分：按月 / 验收 / 用量</td>
          </tr>
          <tr>
            <td><strong>= 递延余额（合同负债）</strong></td>
            <td class="num"><strong>{{ fmt(contract.totals.deferred_balance) }}</strong></td>
            <td class="muted" style="text-align:left">正数：已收款未履约；负数：已履约未收足款</td>
          </tr>
          <tr>
            <td>分摊总额 − 已确认</td>
            <td class="num">{{ fmt(contract.totals.remaining_obligation) }}</td>
            <td class="muted" style="text-align:left">剩余履约义务（含未验收实施、未开通订阅、未发生用量）</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>收款记录</h3>
      <table>
        <thead><tr><th>收款日期</th><th>金额</th><th>收款单号</th></tr></thead>
        <tbody>
          <tr v-for="p in contract.payments" :key="p.id">
            <td>{{ p.received_on }}</td>
            <td class="num">{{ fmt(p.amount) }}</td>
            <td>{{ p.reference || '—' }}</td>
          </tr>
          <tr v-if="!contract.payments.length">
            <td colspan="3" class="muted" style="text-align:left">暂无收款</td>
          </tr>
        </tbody>
      </table>
      <div class="form-row">
        <input type="date" v-model="paymentForm.received_on" />
        <input type="number" min="0.01" step="0.01" placeholder="金额" v-model="paymentForm.amount" style="width:130px" />
        <input placeholder="收款单号" v-model="paymentForm.reference" style="width:140px" />
        <button :disabled="busy" @click="addPayment">登记收款</button>
        <span class="muted">登记收款只改变递延余额，不确认收入</span>
      </div>
    </div>

    <div class="card" v-if="implLines.length || usageLines.length">
      <h3>业务动作</h3>
      <div v-for="line in implLines" :key="'a' + line.id" class="action-block">
        <strong>#{{ line.sort }} {{ line.name }}</strong>
        <span class="badge wait" v-if="!line.acceptance">待验收</span>
        <span class="badge ok" v-else>已验收</span>
        <div class="form-row" v-if="!line.acceptance">
          <input type="date" v-model="acceptForms[line.id].accepted_on" />
          <input placeholder="验收单号" v-model="acceptForms[line.id].reference" style="width:150px" />
          <input placeholder="说明（可选）" v-model="acceptForms[line.id].note" style="width:200px" />
          <button :disabled="busy" @click="addAcceptance(line)">录入验收证据并确认</button>
        </div>
      </div>
      <div v-for="line in usageLines" :key="'u' + line.id" class="action-block">
        <strong>#{{ line.sort }} {{ line.name }}</strong>
        <span class="muted">已录用量 {{ fmt(lineUsageTotal(line)) }} {{ line.unit_label }}</span>
        <div class="form-row">
          <input placeholder="期间 YYYY-MM" v-model="usageForms[line.id].period" style="width:120px" />
          <input type="number" min="0.01" step="0.01" placeholder="用量" v-model="usageForms[line.id].quantity" style="width:110px" />
          <button :disabled="busy" @click="addUsage(line)">录入用量并确认</button>
          <span class="muted">按 用量 × 分摊单价 {{ line.usage_unit_price }} 确认，累计不超过分摊价</span>
        </div>
        <table v-if="line.usage_records.length" style="margin-top:8px">
          <thead><tr><th>期间</th><th>用量</th><th>录入日期</th></tr></thead>
          <tbody>
            <tr v-for="r in line.usage_records" :key="r.id">
              <td>{{ r.period }}</td>
              <td class="num">{{ fmt(r.quantity) }} {{ line.unit_label }}</td>
              <td>{{ r.recorded_on }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="error" class="error-box">{{ error }}</div>
    <div style="margin-top:14px"><router-link to="/">← 返回总览</router-link></div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api, fmt } from '../api'

const props = defineProps({ id: { type: String, required: true } })

const contract = ref(null)
const error = ref('')
const busy = ref(false)
const paymentForm = reactive({ received_on: '', amount: '', reference: '' })
const acceptForms = reactive({})
const usageForms = reactive({})

const sumSsp = computed(() =>
  (contract.value?.lines || []).reduce((s, l) => s + Number(l.ssp), 0)
)
const implLines = computed(() =>
  (contract.value?.lines || []).filter((l) => l.line_type === 'IMPLEMENTATION')
)
const usageLines = computed(() =>
  (contract.value?.lines || []).filter((l) => l.line_type === 'USAGE')
)

function lineUsageTotal(line) {
  return line.usage_records.reduce((s, r) => s + Number(r.quantity), 0)
}

async function run(fn) {
  busy.value = true
  error.value = ''
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function load() {
  contract.value = await api.contract(props.id)
  for (const line of contract.value.lines) {
    if (line.line_type === 'IMPLEMENTATION' && !acceptForms[line.id]) {
      acceptForms[line.id] = reactive({ accepted_on: '', reference: '', note: '' })
    }
    if (line.line_type === 'USAGE' && !usageForms[line.id]) {
      usageForms[line.id] = reactive({ period: '', quantity: '' })
    }
  }
}

const recognize = (period) => run(() => api.recognizePeriod(props.id, period))
const addPayment = () =>
  run(async () => {
    await api.addPayment(props.id, { ...paymentForm })
    paymentForm.amount = ''
    paymentForm.reference = ''
  })
const addAcceptance = (line) => run(() => api.addAcceptance(line.id, { ...acceptForms[line.id] }))
const addUsage = (line) =>
  run(async () => {
    await api.addUsage(line.id, { ...usageForms[line.id] })
    usageForms[line.id].quantity = ''
  })

onMounted(() => run(load))
</script>

<style scoped>
.headline { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 8px; }
.hl-label { font-size: 12px; color: #8a94a3; }
.hl-value { font-size: 20px; font-weight: 700; margin-top: 2px; }
.ok-text { color: #177245; }
.warn-text { color: #b35c00; }
.action-block { border-top: 1px dashed #e5e9f0; padding: 10px 0; }
.action-block:first-of-type { border-top: 0; }
a { color: #0f4c81; }
tfoot td { border-top: 2px solid #dfe5ec; }
</style>
