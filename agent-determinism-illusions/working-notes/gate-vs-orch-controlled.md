# 对照实验笔记：闸门 vs 纯编排（补缺口 1/2/5）

> **日期：** 2026-07-22  
> **脚本：** `scripts/gate-vs-orch-controlled.py`  
> **结果：**  
> - L0/L1：早期 `gate-vs-orch-controlled_result.json`（SKIP）  
> - **L2+business：** `gate-vs-orch-controlled_both_l2_result.json`

## 假说

| ID | 内容 | SKIP_LLM | LIVE L2 + both suite |
|----|------|----------|----------------------|
| H1 | GATE FA &lt; ORCH | ✓ 0% vs 100% | ✓ 0/20 vs 20/20 |
| H2 | late-accept | ✓ | skipped（本跑） |
| H3 | 消融 | ✓ | ✓ |
| H4 | L2 下 FR 可测且 &lt;50% | 不可测（FR n=0） | ✓ **4/19=21.1%** Wilson [8.5%, 43.3%] |

## LIVE L2 要点（严苛）

- 凭证：`cc-switch:Zhipu GLM copy` / glm-5.2（urllib，无 anthropic 包）
- suite=`both`：P1/P4/write-test + **business-proxy**（is_even/fizzbuzz/group_by/测试日志手标注）
- **假拒绝终于可测**：应过 19 条出判定，拒 4 条 → 21.1%
- 仍有 1 条应过 → UNCLEAR
- **假接受仍 0/20**（L0/L1/L2 合计）

## 诚实边界

- business-proxy ≠ 私有生产流量  
- H4 阈值 50% 是工程上界，不是理论最优  
- 未做多重检验校正；L2 投票 N_RUNS=3，本跑约 7 分钟

## 对论文缺口

| 缺口 | 状态 |
|------|------|
| 1 对照 | ✓ 有 |
| 2 外部效度 | △ 有 business-proxy，仍非客户流量 |
| 5 统计/消融 | ✓ Wilson + 消融；L2 FR 有 CI |

**客观一句：** L2 假拒绝洞补上了；「真实业务集」补的是加强代理，不是客户生产集。
