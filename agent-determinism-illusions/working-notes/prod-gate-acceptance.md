# 生产前期验证：闸门先于编排（A/B/C/D）

> **日期：** 2026-07-22  
> **脚本：** `scripts/prod-gate-acceptance.py`  
> **结果：** `scripts/results-v2/prod-gate-acceptance_result.json`

## 命题

能力可以厚；**harness 必须先是闸门**。本验收在四条代表生产路径上证伪「编排可绕过闸门」。

## 四臂

| 臂 | 路径 | 闸门点 |
|----|------|--------|
| A | 写文件 + 跑测试 | 真 unittest；垃圾日志 L0；慢调用 PHYSICAL_TIMEOUT |
| B | 多文件交付 | forge L0/L1 拒垃圾/TODO/鸭子文 |
| C | 短工具环 | 押金 / 惊跳 / wind_down |
| D | 仓内 phasegate 入口 | 外层 L0 仍拒形式主义垃圾；包装押金；超时先于 verify |

## 运行

```powershell
cd agent-determinism-illusions/scripts
$env:SKIP_LLM="1"
python prod-gate-acceptance.py
# 可选真模型烟测
python prod-gate-acceptance.py --live-llm
```

## 立场

`stance`: capabilities may be thick; harness must be a gate first.
