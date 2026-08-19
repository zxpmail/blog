# 测量工具盲区清单（焊死笔记）

Date: 2026-08-17  
Status: working-note（可引用索引；不是正式 Part）  
总钉：把每一个「测量工具本身的盲区」抠出来焊死，否则永远困在「测试全绿，上线崩塌」。

相关：`three-legs-agent-eval.md`（先验信道 + 三腿）。本页专收**仪器/对照/报告自身的洞**，不是业务缺陷目录。

## 总命题

绿的是测量，崩的是世界。若仪器、对照、戳记、法定人数验证与被测代码共盲区，绿只会越来越会骗人。焊盲区 = 让「假绿 / 假红 / 假齐全」在打印前过不了门闩——不是宣称系统已安全。

## 盲区表（已命名 + 已跑形状）

| # | 测量工具在骗什么 | 看起来像 | 焊法（操作门闩） | 证据脚本 / 落地 |
|---|------------------|----------|------------------|-----------------|
| 1 | 通过率 / 只接受型验证器 | 越测越绿 | 破坏样必须打零才准印通过率 | `wrong-tool-negative-control-test.py` |
| 2 | 手写负对照 / 手写套件 | 作者期望点全绿 | 语料基率：总体不能近全一 | `supersession-hand-vs-corpus-test.py` |
| 3 | 无信号当健康 | catches=0 / downgrades=0 | 活性探针或显式 `ran`；§9 ESCALATE | `absence-not-health-test.py` |
| 4 | 对照读错信道 | 健康卫士被报 BROKEN | 对照与仪器约定同一信道 | `control-channel-mismatch-test.py` |
| 5 | 注册 ≠ 开火 | 规则文件静态全绿 | 按效果验 | 同上 R 格 |
| 6 | 复合章 / 写完盖章 | 装新鲜 | t0 偏旧是界；跨消费者阈值才「值钱」 | `composite-stamp-*` / `start-stamp-*` / `stamp-spread-vs-threshold-test.py` |
| 7 | 章只说年龄 | 新鲜且齐全 | 打印触及的 store；联结覆盖；required 从 store 枚举非 reader 自报 | `stamp-partial-store-read-test.py` |
| 7b | 章不说运行种类 | drill COUNT 诚实、VERDICT 假 critical | 正文自签 `run_kind`；ingest 丢弃 drill | `stamp-provenance-drill-test.py` |
| 8 | 外钉只证曾批准 | 选型回滚假绿 | 密封 minimum + 独立授权跃迁 | `parent-pin-rollback-test.py` |
| 9 | 单视图 consistency | 两首次 job 双绿 | 见证 gossip；再要交点条件 | `parent-pin-equivocation-*` / `witness-freshness` / `byzantine-quorum` |
| 10 | 2/3 裸阈值 | 双签仍双绿 | f=1 → 3/4 交点 | `parent-pin-byzantine-quorum-test.py` |
| 11 | CI 门 + 同仓 DEV 钥 | 缺收据会红（有用）但仍可自签 | 外置钥与验证；三旁路夹具钉残差 | ReqForge `policy-witness-quorum` + `policy-witness-self-authorship.test.ts` |
| 12 | 报告通道可写 | 父进程/digest 假绿 | 报告权、外钉不可合写 | `parent-reporting-*` / `parent-oracle-hollow` / `parent-residual-*` |

## 尚未焊死（诚实残差）

- 见证钥与法定人数验证仍在候选 job 信任域内（夹具已证可自签；protected workflow 未落地）  
- 见证集 / 密钥轮换的完整 append-only 登记  
- 真 BFT / 非共谋证明  
- 现场发生率（所有 SUPPORT 皆合成形状）  
- 「焊死」≠ 穷尽一切未命名盲区——新同义词、新联结、新对照信道会再开洞；纪律是持续抠，不是一次闭合  

## 判据（何时算焊上了一道）

同时满足才算「这道仪器盲区有操作焊点」：

1. 有命名形状（能复述「骗的是什么」）  
2. 有负对照或结构门，使假绿/假红/假齐全至少在合成目录上可红  
3. 回帖/笔记不把 SUPPORT 说成安全证明  

CI 真红（如 forge-smoke 缺收据）是加分，不是唯一标准；同信任域自签说明 usefulness ≠ 生产边界。

## 回帖挂钩（本轮相关）

- Tom 信道：`reply-tom-jones-control-channel.md`  
- Tom 部分读取：`reply-tom-jones-partial-store.md`；round-2 `reply-tom-jones-partial-store-round2.md`（U/W + provenance）  
- Peter 自签：`reply-peter-self-authorship.md`  
- 三腿：`three-legs-agent-eval.md`  

## 升格条件

读者第二次要「整张盲区图」或正式 Part 收束时，以本表为目录升格；升格时核对每行脚本路径仍有效，并单列「未焊残差」。
