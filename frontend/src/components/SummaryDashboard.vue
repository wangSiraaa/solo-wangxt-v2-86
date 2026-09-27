<script setup>
defineProps({
  data: Object,
  asOf: String,
});
defineEmits(["open"]);
</script>

<template>
  <div v-if="data">
    <div class="cards">
      <div class="card">
        <div class="label">签约合同金额</div>
        <div class="value">¥{{ data.totals.signed_amount }}</div>
      </div>
      <div class="card received">
        <div class="label">累计收款（截至 {{ data.as_of }}）</div>
        <div class="value">¥{{ data.totals.received_amount }}</div>
      </div>
      <div class="card recognized">
        <div class="label">已确认收入（截至 {{ data.as_of }}）</div>
        <div class="value">¥{{ data.totals.recognized_revenue }}</div>
      </div>
      <div class="card deferred">
        <div class="label">递延余额（收款−确认）</div>
        <div class="value">¥{{ data.totals.deferred_balance }}</div>
      </div>
    </div>

    <div class="section">
      <h3>逐合同三账对照（点击行下钻合同项）</h3>
      <table>
        <thead>
          <tr>
            <th>合同编号</th>
            <th>客户</th>
            <th class="num">签约金额</th>
            <th class="num">开票金额</th>
            <th class="num">收款金额</th>
            <th class="num">已确认收入</th>
            <th class="num">递延余额</th>
            <th class="num">合同负债</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in data.contracts"
            :key="row.contract_id"
            class="clickable"
            @click="$emit('open', row.contract_id)"
          >
            <td>{{ row.number }}</td>
            <td>{{ row.customer }}</td>
            <td class="num">{{ row.signed_amount }}</td>
            <td class="num">{{ row.billed_amount }}</td>
            <td class="num">{{ row.received_amount }}</td>
            <td class="num" style="color:#047857;font-weight:600">{{ row.recognized_revenue }}</td>
            <td class="num" style="color:#b45309">{{ row.deferred_balance }}</td>
            <td class="num">{{ row.contract_liability }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr style="font-weight:700;background:#f8fafc">
            <td colspan="2">合计</td>
            <td class="num">{{ data.totals.signed_amount }}</td>
            <td class="num">{{ data.totals.billed_amount }}</td>
            <td class="num">{{ data.totals.received_amount }}</td>
            <td class="num">{{ data.totals.recognized_revenue }}</td>
            <td class="num">{{ data.totals.deferred_balance }}</td>
            <td class="num">{{ data.totals.contract_liability }}</td>
          </tr>
        </tfoot>
      </table>
      <div class="deferred-note">
        提示：「开票金额」与「已确认收入」不同口径——例如 HT-2026-C03 在 10 月已全额开票收款、
        但服务未开通，确认收入为 0，全部是递延。
      </div>
    </div>
  </div>
</template>
