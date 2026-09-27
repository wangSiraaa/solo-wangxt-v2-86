# 收入确认核算应用（账号订阅 / 一次性实施 / 按量服务）

把财务的三条线彻底分开：

1. **签了多少合同** —— 合同固定对价与各履约义务的独立售价（SSP）；
2. **收了多少钱 / 开了多少票** —— 现金与开票口径（**开票不等于收入**）；
3. **当期真正履约确认了多少收入** —— 订阅按月、实施凭验收证据、按量凭已录入用量。

> ⚠️ 本项目中的分摊与确认规则是**题目给定的示例政策，仅用于本项目演示，不宣称覆盖任何会计准则。**

## 技术栈

- 后端：Django 5 + Django REST Framework，所有金额用 `Decimal`（`max_digits=14, decimal_places=2`）计算，`ROUND_HALF_UP`，尾差由最后一项吸收
- 数据库：PostgreSQL（履约义务、独立售价、分摊价、确认依据都落库）
- 前端：Vue 3（组合式 API）+ Vite，负责合同组成与递延余额对照，可从汇总下钻到合同项的每一条确认计划与确认依据

## 示例政策

### 交易价格分摊（相对独立售价比例法）

```
SSP_i = SSP单价 × 计量数量（订阅按服务月数、实施按项目数、按量按预估用量）
分摊_i = round(合同固定对价 × SSP_i / ΣSSP, 2)      # 最后一项吸收尾差
```

### 确认计划

| 履约义务 | 确认方式 | 待确认的处理 |
| --- | --- | --- |
| 账号订阅 | 分摊价 ÷ 服务月数，逐自然月确认（月末为确认依据日，最后一月吸收尾差） | 未到期的月份保持待确认 |
| 一次性实施 | 每录入一份验收证据确认「分摊价 × 验收比例」 | **没有验收证据的部分保持待确认**（确认依据：待录入验收证据） |
| 按量服务 | 分摊单价（分摊价 ÷ 预估总量）× **已录入用量**，用量月末确认 | 已预收/已分摊但未发生用量的部分保持待确认（预收未开通即 0 确认） |

所有确认行都带**确认依据**（验收单据号/用量单据号/订阅服务月），页面可从合同汇总追到合同项再到依据。

统一的截止日门控：一行只有在 `确认依据日 ≤ 核算截止日` 时才算已确认——所以 11 月才录入的用量不会提前确认进 10 月。

### 余额对照口径

- 递延余额（现金口径）= 累计收款 − 已确认收入
- 合同负债 = 合同固定对价 − 已确认收入
- 已开票未确认 = 累计开票 − 已确认收入（仅用于核对「开票≠收入」）

## 三组虚构案例（`seed_demo` 灌入，`verify_demo` 逐期断言）

### A. 跨月订阅 `HT-2026-A01`（蓝鲸电商）

合同 117,000（SSP 120,000，折扣 15,000）；订阅 4/1–7/31（SSP 90,000）+ 实施（SSP 30,000，4/20 全验收）；4 月全额开票全额收款。

| 截止日 | 已确认收入 | 递延余额 | 说明 |
| --- | ---: | ---: | --- |
| 2026-03-31 | 0.00 | 0.00 | 未签履约，票/款均未发生 |
| 2026-04-30 | 51,187.50 | 65,812.50 | 实施 29,250 + 订阅 21,937.50 |
| 2026-05-31 | 73,125.00 | 43,875.00 | +订阅 21,937.50 |
| 2026-07-31 | 117,000.00 | 0.00 | 4 个订阅月全部确认 |

分摊：订阅 87,750.00（90,000/120,000 × 117,000）、实施 29,250.00。

### B. 部分验收 `HT-2026-B02`（赤兔物流）

合同 150,000（SSP 160,000）；订阅全年 1–12 月（SSP 120,000）+ 实施两期（SSP 40,000，**仅一期 60% 于 3/15 验收，二期无证据**）。

| 截止日 | 已确认收入 | 其中 | 递延余额（收款−确认） |
| --- | ---: | --- | ---: |
| 2026-03-31 | 50,625.00 | 订阅 3×9,375 + 实施 22,500 | 99,375.00 |
| 2026-07-31 | 88,125.00 | 订阅 7×9,375 + 实施 22,500 | 141,875.00 |
| 2026-09-30 | 106,875.00 | 订阅 9×9,375 + 实施 22,500 | 123,125.00 |
| 2026-12-31 | 135,000.00 | 订阅 112,500 + 实施仅 22,500；**剩余 15,000 无验收证据，永不确认** | 95,000.00 |

二期开票 30,000、多收款 10,000 都不改变收入：7 月开票时收入仍只有已履约部分。

### C. 预收未开通 `HT-2026-C03`（云杉智能）

按量预存 90,000（SSP 0.90/次 × 预估 100,000 次，无折扣）；9 月签约即全额开票、全额收款（预收），**11 月才开通并录入 60,000 次用量**。

| 截止日 | 已确认收入 | 递延余额 | 说明 |
| --- | ---: | ---: | --- |
| 2026-09-30 | 0.00 | 90,000.00 | 已开票已收款，服务未开通 |
| 2026-10-31 | 0.00 | 90,000.00 | 无用量记录 → 0 确认 |
| 2026-11-30 | 54,000.00 | 36,000.00 | 0.90 × 60,000；剩余 36,000 待用量 |

## 目录结构

```
backend/
  accounting/
    models.py            # 合同/履约义务/SSP/验收证据/用量/开票/收款/确认计划行
    services.py          # Decimal 分摊与确认计划引擎（幂等重建）
    serializers.py       # 截止日门控 line_is_recognized
    views.py             # 合同明细、三账汇总、全量计划、证据/用量录入触发重建
    management/commands/
      seed_demo.py       # 三组虚构案例
      verify_demo.py     # 逐期断言核对
    tests.py             # 引擎单元测试（7 个）
frontend/
  src/
    App.vue                       # 截止日切换 + 合同列表/总览/计划
    components/SummaryDashboard.vue   # 合同金额·收款·确认收入·递延 总览
    components/ContractDetail.vue     # 合同组成、SSP/分摊、确认计划下钻、录入证据/用量
    components/RecognitionTable.vue   # 全部确认计划（可按类型/状态过滤）
scripts/start.sh         # 免 root 启动 PG + migrate + seed + verify + runserver
```

## 运行

### 环境准备（本沙箱已执行；无 root 环境）

```bash
# 1) Python 包（用户态）
python3 /tmp/get-pip.py --user --break-system-packages
python3 -m pip install --user --break-system-packages django djangorestframework "psycopg[binary]"

# 2) PostgreSQL 15（Debian 12 aarch64 示例；把 .deb 解包到家目录，免 root）
mkdir -p ~/pgdebs ~/pgsql
# 下载 postgresql-15 与 postgresql-client-15 的 arm64 .deb 到 ~/pgdebs
for d in ~/pgdebs/*.deb; do dpkg-deb -x "$d" ~/pgsql; done
~/pgsql/usr/lib/postgresql/15/bin/initdb -D ~/pgdata -U postgres --auth=trust
printf "port = 5439\nlisten_addresses = ''\nunix_socket_directories = '/tmp'\n" >> ~/pgdata/postgresql.conf
~/pgsql/usr/lib/postgresql/15/bin/pg_ctl -D ~/pgdata -l ~/pgdata/pg.log start
~/pgsql/usr/lib/postgresql/15/bin/createdb -h /tmp -p 5439 -U postgres revenue

# 3) 前端
cd frontend && npm install && npm run build   # 产物输出到 backend/frontend_dist
```

### 启动

```bash
bash scripts/start.sh        # migrate + seed_demo + verify_demo + http://127.0.0.1:8000/
```

前端开发模式（热更新，API 代理到 8000）：

```bash
cd frontend && npm run dev   # http://127.0.0.1:5173
```

### 核对与测试

```bash
cd backend
python3 manage.py verify_demo     # 三组案例逐期 PASS/FAIL 断言
python3 manage.py test accounting # 引擎单元测试
```

页面用法：顶部切换「核算截止日」即可逐期回放；进入合同后点「确认计划 ▸」可看每一行的金额/状态/确认依据，并可在实施项下补录验收证据、在按量项下补录用量，提交后后端自动重建该合同项的确认计划。

### 主要 API

| 方法 & 路径 | 作用 |
| --- | --- |
| `GET /api/summary/?as_of=YYYY-MM-DD` | 三账汇总（签约/开票/收款/确认/递延/合同负债） |
| `GET /api/contracts/` / `POST` | 合同及履约义务（创建时自动按 SSP 分摊并生成计划） |
| `GET /api/contracts/{id}/check_plan/?as_of=...` | 合同组成 + 每合同项确认进度 + 计划行依据 + 票款 |
| `POST /api/contracts/{id}/evidences` | 录入验收证据（自动重建实施项计划，累计比例 ≤100% 校验） |
| `POST /api/contracts/{id}/usage` | 录入用量（自动重建按量项计划） |
| `GET /api/recognition/?as_of=...` | 全部确认计划行 |
| `POST /api/rebuild/` | 全量重建 |

## 设计要点

- **开票不参与任何确认金额计算**：`Invoice`/`Payment` 只出现在余额对照里；收入只由履约义务的确认计划行决定。
- **全部 Decimal**：分摊、月度均摊、验收比例、用量单价均在 Python `Decimal` + `ROUND_HALF_UP` 下完成，金额列为 PG `numeric(14,2)`；两处尾差（分摊、月数均分）都由最后一项吸收，保证「Σ 分摊 = 合同对价」「Σ 月额 = 分摊价」。
- **幂等重建**：录入/修改/删除证据或用量后，先删后建该义务的全部确认行；`basis` 字段留存确认依据，外键回指验收/用量单据。
- **截止日回放**：计划行一次生成，状态在查询时按 `period_end ≤ as_of` 即时计算，支持逐期核对而不改数据。
