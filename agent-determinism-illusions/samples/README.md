# samples/ — Agent Quality Inspector 测试场景

本目录包含系列文章中所有实验的**输入样本**（场景定义、测试数据），与 `scripts/` 中的可执行实验代码分离。

每个 JSON 文件可直接作为实验脚本的输入，方便你替换自己的业务数据重新测试。

## 文件索引

| 文件 | 对应实验 | 对应文章 | 内容 |
|------|---------|---------|------|
| `scenarios-harness-verify.json` | 实验 E (harness-verify-test.py) | 续二 (Part 3) | 8 场景：4 合法产物 + 4 垃圾产物，用于 LLM 质检员精度-召回率权衡测量 |
| `scenarios-phase-gate.json` | 实验 C (phasegate-formalism-test.py) | 主文 (Part 1) | 8 场景：4 内容正确 + 4 内容垃圾但符合 Gate 检查，用于 Phase Gate 假阳率证伪 |

## 运行方式

```bash
# 例：用自定义场景跑 harness-verify-test
python scripts/harness-verify-test.py --scenarios samples/scenarios-harness-verify.json

# 例：用自定义场景跑 phase-gate 测试
python scripts/phasegate-formalism-test.py --scenarios samples/scenarios-phase-gate.json
```

## 场景结构

每个场景文件是 JSON 数组，每项包含：

```json
{
  "id": "L1",
  "task": "任务描述，发给 LLM",
  "content": "产物内容（文本）",
  "legitimate": true,
  "notes": "可选的备注，如 '内容完整，符合要求'"
}
```

- `legitimate: true` → 该产物内容正确，应被质检通过
- `legitimate: false` → 该产物内容垃圾，应被质检拦截

## 扩展

添加你自己的场景到 JSON 数组即可。实验脚本会自动：
1. 读取所有场景
2. 对每个场景调用目标模型（质检 LLM 或 Phase Gate）
3. 输出混淆矩阵（真阳 / 假阳 / 真阴 / 假阴）

## 许可

与仓库主体一致。欢迎 fork、修改、PR。
