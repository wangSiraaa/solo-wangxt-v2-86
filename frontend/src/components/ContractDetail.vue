<script setup>
import { ref } from "vue";
import { api } from "../api.js";

const props = defineProps({
  data: Object,
  asOf: String,
});
const emit = defineEmits(["changed"]);

const expanded = ref({}); // obligation id -> bool
const error = ref("");
const busy = ref(false);

const evidenceForm = ref({});
const usageForm = ref({});

const typeLabel = {
  subscription: "账号订阅",
  implementation: "一次性实施",
  usage: "按量服务",
};

function toggle(id) {
  expanded.value[id] = !expanded.value[id];
}

async function addEvidence(o) {
  error.value = "";
  const f = evidenceForm.value[o.id] || {};
  if (!f.accepted_on || !f.portion || !f.document_ref) {
    error.value = "请填写验收日期、验收比例与单据号。";
    return;
  }
  busy.value = true;
  try {
    await api.addEvidence(props.data.id, {
      obligation: o.id,
      accepted_on: f.accepted_on,
      portion: f.portion,
      document_ref: f.document_ref,
      note: f.note || "",
    });
    evidenceForm.value[o.id] = {};
    emit("changed");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}

async function addUsage(o) {
  error.value = "";
  const f = usageForm.value[o.id] || {};
  if (!f.usage_month || !f.quantity || !f.source_ref) {
    error.value = "请填写用量月份、用量与单据号。";
    return;
  }
  busy.value = true;
  try {
    await api.addUsage(props.data.id, {
      obligation: o.id,
      usage_month: f.usage_month + "-01",
      quantity: f.quantity,
      source_ref: f.source_ref,
    });
    usageForm.value[o.id] = {};
    emit("changed");
  } catch (e) {
    error.value = e.message;
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div v-if="data">
    <div class="cards">
      <div class="card">
        <div class="label">合同金额（签约）</div>
        <div class="value">¥{{ data.totals.signed_amount }}</div>
      </div>
      <div class="card received">
        <div class="label">收款金额</div>
        <div class="value">¥{{ data.totals.received_amount }}</div>
      </div>
      <div class="card recognized">
        <div class="label">已确认收入</div>
        <div class="value">¥{{ data.totals.recognized_revenue }}</div>
      </div>
      <div class="card deferred">
        <div class="label">递延余额（现金口径）</div>
        <div class="value">¥{{ data.totals.deferred_balance }}</div>
      </div>
    </div>

    <p class="muted" style="margin:-6px 0 14px">
      {{ data.number }} · {{ data.customer }} · 签订于 {{ data.signed_on }} ·
      截止日 {{ data.as_of }} ·
      开票 ¥{{ data.totals.billed_amount }}（不等于收入） ·
      已开票未确认 ¥{{ data.totals.billed_not_recognized }} ·
      合同负债 ¥{{ data.totals.contract_liability }}
    </p>
    <p v-if="error" class="error">{{ error }}</p>

    <!-- 合同组成：履约义务 / SSP / 分摊价 / 确认进度 -->
    <div class="section">
      <h3>合同组成与各合同项确认进度（可下钻确认计划与依据）</h3>
      <table>
        <thead>
          <tr>
            <th>合同项</th>
            <th>类型</th>
            <th>服务期间</th>
            <th class="num">独立售价 SSP</th>
            <th class="num">分摊交易价格</th>
            <th class="num">已确认</th>
            <th class="num">递延</th>
            <th></th>
          </tr>
        </thead>
        <template v-for="o in data.obligations" :key="o.id">
          <tr>
            <td><b>{{ o.code }}</b> {{ o.name }}</td>
            <td><span class="tag" :class="o.obligation_type">{{ typeLabel[o.obligation_type] }}</span></td>
            <td>
              <template v-if="o.obligation_type === 'usage'">按量，单位：{{ o.usage_unit }}</template>
              <template v-else>{{ o.service_start }} ~ {{ o.service_end }}</template>
            </td>
            <td class="num">{{ o.standalone_selling_price }}</td>
            <td class="num"><b>{{ o.allocated_price }}</b></td>
            <td class="num" style="color:#047857;font-weight:600">{{ o.recognized_amount }}</td>
            <td class="num" style="color:#b45309">{{ o.deferred_amount }}</td>
            <td><span class="clickable" @click="toggle(o.id)">{{ expanded[o.id] ? '收起' : '确认计划 ▸' }}</span></td>
          </tr>
          <tr v-if="expanded[o.id]" class="expand-row">
            <td colspan="8">
              <table style="box-shadow:none">
                <thead>
                  <tr>
                    <th>确认期间 / 依据日</th>
                    <th class="num">金额</th>
                    <th>状态</th>
                    <th>确认依据</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="line in o.lines" :key="line.id">
                    <td>
                      <template v-if="line.period_end">{{ line.period_start || '—' }} ~ {{ line.period_end }}</template>
                      <template v-else>无固定日期（条件未满足）</template>
                    </td>
                    <td class="num">{{ line.amount }}</td>
                    <td><span class="tag" :class="line.status">{{ line.status === 'recognized' ? '已确认' : '待确认' }}</span></td>
                    <td class="basis">{{ line.basis }}</td>
                  </tr>
                </tbody>
              </table>

              <!-- 录入验收证据 -->
              <div v-if="o.obligation_type === 'implementation'" class="inline-form">
                <b>录入验收证据：</b>
                <input type="date" v-model="(evidenceForm[o.id] ||= {}).accepted_on" />
                <input type="number" step="0.0001" min="0" max="1" placeholder="验收比例 0~1"
                       v-model="(evidenceForm[o.id] ||= {}).portion" style="width:130px" />
                <input placeholder="验收单据号" v-model="(evidenceForm[o.id] ||= {}).document_ref" />
                <input placeholder="说明（可选）" v-model="(evidenceForm[o.id] ||= {}).note" style="width:200px" />
                <button class="btn" :disabled="busy" @click="addEvidence(o)">提交并重算</button>
              </div>

              <!-- 录入用量 -->
              <div v-if="o.obligation_type === 'usage'" class="inline-form">
                <b>录入已发生用量：</b>
                <input type="month" v-model="(usageForm[o.id] ||= {}).usage_month" />
                <input type="number" step="0.01" min="0" placeholder="用量"
                       v-model="(usageForm[o.id] ||= {}).quantity" style="width:130px" />
                <input placeholder="用量单据号" v-model="(usageForm[o.id] ||= {}).source_ref" />
                <button class="btn" :disabled="busy" @click="addUsage(o)">提交并重算</button>
              </div>
            </td>
          </tr>
        </template>
      </table>
      <div class="deferred-note">
        分摊校验：Σ 各合同项分摊价 = ¥{{ data.allocated_total }}，与合同金额一致（尾差由最后一项吸收）。
      </div>
    </div>

    <div class="two-col">
      <!-- 开票：不是收入 -->
      <div class="section">
        <h3>开票记录（仅核对口径，<span style="color:#b91c1c">开票≠收入</span>）</h3>
        <table>
          <thead><tr><th>开票日期</th><th class="num">金额</th><th>说明</th></tr></thead>
          <tbody>
            <tr v-for="i in data.invoices" :key="i.id">
              <td>{{ i.issued_on }}</td>
              <td class="num">{{ i.amount }}</td>
              <td class="basis">{{ i.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 收款 / 预收 -->
      <div class="section">
        <h3>收款记录（含预收）</h3>
        <table>
          <thead><tr><th>收款日期</th><th class="num">金额</th><th>性质</th><th>说明</th></tr></thead>
          <tbody>
            <tr v-for="p in data.payments" :key="p.id">
              <td>{{ p.received_on }}</td>
              <td class="num">{{ p.amount }}</td>
              <td><span class="tag" :class="p.is_prepayment ? 'pending' : 'recognized'">
                {{ p.is_prepayment ? '预收' : '正常回款' }}
              </span></td>
              <td class="basis">{{ p.note }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
