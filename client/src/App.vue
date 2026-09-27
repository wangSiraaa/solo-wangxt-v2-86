<template>
  <div class="page">
    <header class="topbar">
      <router-link to="/" class="brand">收入确认核算</router-link>
      <span class="tagline">签了多少合同 · 收了多少钱 · 当期真正履约确认了多少收入</span>
    </header>
    <div class="disclaimer">
      示例政策：相对独立售价分摊交易价格；订阅按月直线确认；实施凭验收证据确认，无证据保持待确认；
      按量按已录用量确认；收款只形成递延（合同负债），开票/收款不直接确认为收入。
      以上政策仅用于本项目演示，不宣称覆盖所有会计准则。
    </div>
    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif;
  background: #f4f6f9;
  color: #1f2933;
}
.page { max-width: 1180px; margin: 0 auto; padding: 0 20px 60px; }
.topbar {
  display: flex; align-items: baseline; gap: 16px;
  padding: 18px 0 10px;
}
.brand {
  font-size: 20px; font-weight: 700; color: #0f4c81; text-decoration: none;
}
.tagline { color: #6b7280; font-size: 13px; }
.disclaimer {
  background: #fff8e6; border: 1px solid #f0dfa8; color: #7a5d00;
  border-radius: 8px; padding: 10px 14px; font-size: 12.5px; line-height: 1.7;
  margin-bottom: 18px;
}
main { display: block; }
.card {
  background: #fff; border: 1px solid #e5e9f0; border-radius: 10px;
  padding: 16px 18px; margin-bottom: 16px;
}
.card h3 { margin: 0 0 12px; font-size: 15px; color: #0f4c81; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { padding: 7px 9px; border-bottom: 1px solid #eef1f5; text-align: right; }
th:first-child, td:first-child { text-align: left; }
th { color: #6b7280; font-weight: 600; background: #fafbfc; }
.num { font-variant-numeric: tabular-nums; }
.badge {
  display: inline-block; padding: 1px 8px; border-radius: 999px;
  font-size: 12px; white-space: nowrap;
}
.badge.ok { background: #e3f5e9; color: #177245; }
.badge.wait { background: #fdeaea; color: #b3352b; }
.badge.plan { background: #e8f0fb; color: #2b5cb3; }
button {
  background: #0f4c81; color: #fff; border: 0; border-radius: 6px;
  padding: 6px 14px; font-size: 13px; cursor: pointer;
}
button:disabled { background: #b6c2cf; cursor: not-allowed; }
button.ghost { background: #eef2f7; color: #0f4c81; }
input, select {
  border: 1px solid #d4dae3; border-radius: 6px; padding: 6px 8px; font-size: 13px;
}
.form-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-top: 10px; }
.muted { color: #8a94a3; font-size: 12px; }
.error-box {
  background: #fdeaea; color: #b3352b; border-radius: 6px;
  padding: 8px 12px; font-size: 13px; margin: 8px 0;
}
</style>
