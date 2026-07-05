# 自定义任务文件格式

`redline-v2-experiment.py` 支持通过 `--task-file` 参数加载自定义任务集。

## JSON 格式

```json
{
  "tasks": [
    {
      "id": "my-task-name",
      "desc": "写一个 Python 函数 double(x), 返回 x 的两倍",
      "test_stmt": "print(double(3)); print(double(-2))",
      "expected": "6\n-4"
    }
  ]
}
```

- `id`: 任务标识(打印用)
- `desc`: 发给 LLM 的任务描述
- `test_stmt`: 验证代码正确性的测试语句(嵌入在待测代码之后运行)
- `expected`: 测试语句的预期标准输出

## 运行

```bash
python redline-v2-experiment.py --task-file my_tasks.json
```

会覆盖内置的 3 个默认任务,用自定义任务运行完整的 A/B 对比实验(有红线 vs 自判)。

## 内置测试集

`test_is_even.py` / `test_fizzbuzz.py` / `test_group_by.py` 是人工预先编写的完整测试,覆盖正常输入、边界值和特殊值。这些测试验证的是"需求级正确性"而非"语法正确性"。
