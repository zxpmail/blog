# -*- coding: utf-8 -*-
"""催款场景的规则模拟：本体文字拿不掉开票金额，输入门才拿掉。

对应私有稿《本体、门、人工兜底》第五节「拿催款填一遍」，不读该文件。

主张（来自稿子，不是新测量）：
  「回款不是开票金额」写进本体，并不能阻止使用开票金额。
  用错数靠输入门：这次只准使用权威源上指定的字段。
  第五节里「收款单在哪个字段」「客户编号怎么对上」等格子是空的。
  空格子对应的问题先不许答。

方法：
  一张合成收款单（开票 100000，已入账 40000）。不是真实单据。
  答题器不读本体句子。看见开票金额就用开票金额；只有已入账才用已入账。
  四组：
    ontology_only — 两个金额都看得见，本体句子在场但不删字段
    section5 — 按第五节的空格子，先拒绝
    hide_invoice — 本体句子仍在，开票金额不交给答题器，只给已入账
    field_named — 把「已入账金额」这一格填上。其余空格子仍空

预期：
  ontology_only 话术把开票金额写成已回款，整句对不上。
  section5 没有放行金额，整句对不上。
  hide_invoice 话术是「华兴，已回款40000元」，整句对得上。
  field_named 话术是「已回款40000元」，整句对得上。「这个客户的回款」仍拒绝。

怎么证伪：
  规则模拟不调用模型。加 --llm 用本机 Ollama qwen2.5:7b。
  加 --cc-switch 用 ~/.cc-switch 当前 Claude provider（温度 0，每组 1 次）。
  --llm / --cc-switch 只给否定句，测稿子里的主张，结果写到 *-claim.json。
  --gate 两个金额都留着，加上「这次只准使用已入账金额」，只问这一组，写到 *-gate.json。
  加 --equals 才补「回款就是已入账金额」，写到 *-equals.json。两轮都不覆盖更早的文件。
  话术里的已回款、已入账必须是 40000。标明是开票的 100000 仍算对上。
  没标名字的别的数算对不上。若两组金额都看得见时模型仍把已回款写成 40000，
  「本体文字挡不住用错数」在这一次上不成立。

依赖：仅 Python 标准库。
"""

import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 合成单据。两个数故意不同，答错一眼能看出来。
RECEIPT = {
    "customer_name": "华兴",
    "invoiced": 100000,
    "collected": 40000,
}

ONTOLOGY_SENTENCE = "回款不是开票金额，不是合同金额，不含预收款。"
# 重做时补上的正句。上一轮只给了否定句，小模型把已回款写成了 60000。
EQUALS_SENTENCE = "回款就是已入账金额。"
# 输入门：两个金额都留在单上，但这次只准用已入账。
GATE_SENTENCE = "这次只准使用已入账金额。"

# 第五节里空着的格子。None 表示没填。
SECTION5_EMPTY = {
    "source_field": None,
    "customer_map": None,
    "invoice_match": None,
    "overdue_rule": None,
    "source_lag": None,
}

# 反事实：只把权威字段这一格填上，其余仍空。
FIELD_NAMED = {
    "source_field": "collected",
    "customer_map": None,
    "invoice_match": None,
    "overdue_rule": None,
    "source_lag": None,
}

QUESTIONS = [
    ("this_customer", "这个客户的回款是多少"),
    ("collected_only", "已入账金额是多少"),
    ("invoice_received", "这张发票收到没有"),
    ("overdue", "逾期了吗"),
    ("not_booked", "还没有入账怎么说"),
    ("script", "给一句建议话术"),
]


def visible_fields(cells):
    """输入门：字段格没填，正式金额不放行；填了就只放该字段。"""
    field = cells.get("source_field")
    if field is None:
        return {}
    if field not in RECEIPT:
        return {}
    return {field: RECEIPT[field]}


def refuse_reason(question_id, cells):
    """空格子先拒绝。话术单独核对，不在这里拒绝。"""
    if question_id == "this_customer":
        if cells.get("customer_map") is None:
            return "客户编号怎么对上收款单还没定，不许答「这个客户的回款」"
        if cells.get("source_field") is None:
            return "收款单字段没定，金额不能当正式回答"
    if question_id == "collected_only" and cells.get("source_field") is None:
        return "收款单字段没定，金额不能当正式回答"
    if question_id == "invoice_received":
        return "发票和到账怎么对应还没定，不许答「这张发票收到没有」"
    if question_id == "overdue":
        return "逾期从哪天起算还没定，不许答逾期"
    if question_id == "not_booked" and cells.get("source_lag") is None:
        return "源晚多久还可以接受还没定，「还没有数」不能上线"
    return None


def naive_answer(question_id, visible):
    """模拟用错数的答题器。不读本体句子。开票金额看得见就拿它作答。"""
    if question_id in ("this_customer", "collected_only"):
        if "invoiced" in visible:
            return {"status": "ANSWER", "amount": visible["invoiced"], "used": "invoiced", "detail": f"用了开票金额 {visible['invoiced']}"}
        if "collected" in visible:
            return {"status": "ANSWER", "amount": visible["collected"], "used": "collected", "detail": f"用了已入账金额 {visible['collected']}"}
        return {"status": "ANSWER", "amount": None, "used": "none", "detail": "没有金额可看"}
    if question_id == "invoice_received" and "invoiced" in visible:
        return {"status": "ANSWER", "amount": visible["invoiced"], "used": "invoiced", "detail": "看见开票金额，就答成这张发票收到了"}
    if question_id == "overdue":
        return {"status": "ANSWER", "amount": None, "used": "none", "detail": "没有逾期规则，仍然作答"}
    if question_id == "not_booked" and "invoiced" in visible:
        return {"status": "ANSWER", "amount": visible["invoiced"], "used": "invoiced", "detail": f"用开票金额 {visible['invoiced']} 填了还没有入账的数"}
    return {"status": "ANSWER", "amount": None, "used": "none", "detail": "没有可看的数"}


# 收款单上实际有的行。整句话术只能和这三行对。
RECEIPT_LINES = (
    f"客户：{RECEIPT['customer_name']}",
    f"开票金额：{RECEIPT['invoiced']}",
    f"已入账金额：{RECEIPT['collected']}",
)


def fields_in_view(mode, cells):
    """这一组答题器看得见哪些金额。"""
    if mode == "all":
        return {"invoiced": RECEIPT["invoiced"], "collected": RECEIPT["collected"]}
    if mode == "collected_only":
        return {"collected": RECEIPT["collected"]}
    return visible_fields(cells)


def draft_script(cells, mode):
    """按这一组看得见的数，拼出整句建议话术。"""
    visible = fields_in_view(mode, cells)
    amount = None
    used = None
    if "invoiced" in visible:
        amount = visible["invoiced"]
        used = "invoiced"
    elif "collected" in visible:
        amount = visible["collected"]
        used = "collected"
    names_customer = mode in ("all", "collected_only") or cells.get("customer_map") is not None
    parts = []
    if names_customer:
        parts.append(f"{RECEIPT['customer_name']}")
    if amount is not None:
        parts.append(f"已回款{amount}元")
    else:
        parts.append("已回款")
    script = "，".join(parts) + "。"
    return script, amount, used


def clause_against_receipt(clause):
    """一段话是否就是收款单上的某一行。对不上就写出原因。"""
    if clause == RECEIPT["customer_name"]:
        return True, RECEIPT_LINES[0]
    collected = str(RECEIPT["collected"])
    invoiced = str(RECEIPT["invoiced"])
    if clause == f"已回款{collected}元":
        return True, RECEIPT_LINES[2]
    if clause == f"已回款{invoiced}元":
        return False, f"写的是已回款{invoiced}，收款单上已入账是{collected}，{invoiced}是开票金额"
    if clause == "已回款":
        return False, "只写了已回款，收款单上的已入账金额没有写进这句话"
    return False, "收款单上没有这一句"


def check_script(cells, mode):
    """整句话术对照收款单。有一段对不上，整句就对不上。"""
    script, amount, used = draft_script(cells, mode)
    clauses = [part for part in script.replace("。", "").split("，") if part]
    checked = []
    for clause in clauses:
        ok, line = clause_against_receipt(clause)
        checked.append({"clause": clause, "ok": ok, "line": line})
    failed = [item for item in checked if not item["ok"]]
    if failed:
        detail = "；".join(f"「{item['clause']}」{item['line']}" for item in failed)
        status = "MISMATCH"
    else:
        detail = "整句每一段都在收款单上"
        status = "MATCH"
    return {
        "status": status,
        "amount": amount,
        "used": used,
        "script": script,
        "clauses": checked,
        "detail": f"话术「{script}」{detail}",
    }


def run_arm(name, cells, mode):
    """一组条件。mode 为 all / collected_only / gate。"""
    rows = []
    for qid, text in QUESTIONS:
        if mode == "gate":
            reason = refuse_reason(qid, cells)
            visible = {} if reason else visible_fields(cells)
        else:
            reason = None
            visible = fields_in_view(mode, cells)
        if qid == "script":
            checked = check_script(cells, mode)
            row = {
                "question": text,
                "status": checked["status"],
                "reason": checked["detail"],
                "amount": checked["amount"],
                "used": checked["used"],
                "script": checked["script"],
                "clauses": checked["clauses"],
            }
        elif reason:
            row = {"question": text, "status": "REFUSE", "reason": reason, "amount": None, "used": None}
        else:
            answered = naive_answer(qid, visible)
            row = {"question": text, "reason": answered["detail"], **answered}
        rows.append(row)
    return {"arm": name, "ontology_sentence_present": True, "rows": rows}


def main():
    arms = [
        run_arm("ontology_only", SECTION5_EMPTY, "all"),
        run_arm("section5", SECTION5_EMPTY, "gate"),
        run_arm("hide_invoice", SECTION5_EMPTY, "collected_only"),
        run_arm("field_named", FIELD_NAMED, "gate"),
    ]
    ontology_amount = next(r["amount"] for r in arms[0]["rows"] if r["question"].startswith("已入账"))
    hidden_amount = next(r["amount"] for r in arms[2]["rows"] if r["question"].startswith("已入账"))
    named_amount = next(r["amount"] for r in arms[3]["rows"] if r["question"].startswith("已入账"))
    section5_refuses_customer = next(
        r["status"] == "REFUSE" for r in arms[1]["rows"] if r["question"].startswith("这个客户")
    )
    def script_row(arm):
        return next(r for r in arm["rows"] if r["question"].startswith("给一句"))

    verdict = {
        "ontology_only_uses_invoice": ontology_amount == RECEIPT["invoiced"],
        "section5_refuses_this_customer": section5_refuses_customer,
        "hide_invoice_uses_collected": hidden_amount == RECEIPT["collected"],
        "field_named_uses_collected": named_amount == RECEIPT["collected"],
        "ontology_script_whole_mismatch": script_row(arms[0])["status"] == "MISMATCH",
        "section5_script_whole_mismatch": script_row(arms[1])["status"] == "MISMATCH",
        "hide_invoice_script_whole_match": script_row(arms[2])["status"] == "MATCH",
        "field_named_script_whole_match": script_row(arms[3])["status"] == "MATCH",
    }
    verdict["pass"] = all(verdict.values())
    out = {
        "claim": "本体句子不删除开票金额；第五节空格子拒绝正式回答；话术整句对照收款单，不单比金额",
        "simulator": "naive_prefers_invoice",
        "not_a_model_measurement": True,
        "receipt": RECEIPT,
        "ontology_sentence": ONTOLOGY_SENTENCE,
        "arms": arms,
        "verdict": verdict,
    }
    dest = Path(__file__).parent / "results-v2" / "collection-ontology-gate-sim.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"合成单据：开票 {RECEIPT['invoiced']}，已入账 {RECEIPT['collected']}")
    print(f"本体句子在三组里都在场：{ONTOLOGY_SENTENCE}")
    print("答题器不读这句话。看得见开票金额就用开票金额。")
    print()
    for arm in arms:
        print(f"## {arm['arm']}")
        for row in arm["rows"]:
            detail = row["reason"]
            print(f"  {row['status']:10} {row['question']}  →  {detail}")
        print()
    print(f"判定：{'PASS' if verdict['pass'] else 'FAIL'}")
    print(f"结果：{dest}")


def call_ollama(prompt, model, host):
    """向本机 Ollama 要一句回答。"""
    url = host.rstrip("/") + "/api/chat"
    payload = json.dumps({
        "model": model,
        "stream": False,
        "options": {"temperature": 0},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return (body.get("message") or {}).get("content") or ""


def llm_prompt(lines, use_equals, use_gate):
    """让模型写出已回款金额。正句和输入门都要显式打开。"""
    sheet = "\n".join(lines)
    definition = ONTOLOGY_SENTENCE
    if use_equals:
        definition = EQUALS_SENTENCE + definition
    gate = f"\n\n{GATE_SENTENCE}" if use_gate else ""
    return (
        f"收款单：\n{sheet}\n\n{definition}{gate}\n\n"
        "给业务员写一句可直接使用的话，必须写出已回款金额。"
        "不要写「请核实」，不要解释。"
    )


def judge_llm_script(text):
    """已回款、已入账必须是已入账金额。标明开票的数按开票核对，不能当成写错。"""
    compact = re.sub(r"[\s,，]", "", text)
    collected = RECEIPT["collected"]
    invoiced = RECEIPT["invoiced"]
    booked = [
        int(n)
        for n in re.findall(
            r"(?:(?:已回款|已入账)(?:金额)?|回款金额)[：:为]?(\d+)",
            compact,
        )
    ]
    invoice_said = [
        int(n) for n in re.findall(r"开票(?:金额)?[：:为]?(\d+)", compact)
    ]
    numbers = [int(n) for n in re.findall(r"\d+", compact)]
    if not numbers:
        return "NO_AMOUNT", "没有写出金额"
    if not booked:
        return "NO_AMOUNT", "没有写出已回款金额"
    if any(n != collected for n in booked):
        shown = "、".join(str(n) for n in booked)
        return "MISMATCH", f"已回款写成 {shown}，收款单上已入账是 {collected}"
    if any(n != invoiced for n in invoice_said):
        shown = "、".join(str(n) for n in invoice_said)
        return "MISMATCH", f"开票写成 {shown}，收款单上开票是 {invoiced}"
    leftover = list(numbers)
    for n in booked + invoice_said:
        if n in leftover:
            leftover.remove(n)
    if leftover:
        shown = "、".join(str(n) for n in leftover)
        return "MISMATCH", f"还写了 {shown}，收款单上没有这个数"
    if invoice_said:
        return "MATCH", f"已入账是 {collected}，开票是 {invoiced}"
    return "MATCH", f"已回款金额是已入账 {collected}"


def load_cc_switch():
    """读 cc-switch 当前 provider。不打印 token。"""
    import importlib.util

    path = Path(__file__).with_name("harness-kernel.py")
    spec = importlib.util.spec_from_file_location("harness_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load_cc_switch_provider()


def call_cc_switch(prompt, cfg):
    """按 cc-switch 的接口问一句。"""
    base = cfg["base"].rstrip("/")
    backend = cfg["backend"]
    if backend == "anthropic":
        url = base + "/v1/messages"
        payload = {
            "model": cfg["model"],
            "max_tokens": 1024,
            "temperature": 0,
            "thinking": {"type": "disabled"},
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "x-api-key": cfg["token"],
            "anthropic-version": "2023-06-01",
        }
    else:
        url = base + "/chat/completions"
        payload = {
            "model": cfg["model"],
            "max_tokens": 1024,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['token']}",
        }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:180]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if backend == "anthropic":
        texts = [
            str(block.get("text") or "").strip()
            for block in body.get("content") or []
            if block.get("type") == "text" and str(block.get("text") or "").strip()
        ]
        if texts:
            return "\n".join(texts)
        raise RuntimeError(
            f"没有写出话术（stop={body.get('stop_reason')}）"
        )
    choices = body.get("choices") or []
    if not choices:
        return ""
    return str((choices[0].get("message") or {}).get("content") or "").strip()


def run_llm():
    """三组各问一次模型。默认只给否定句。"""
    use_cc = "--cc-switch" in sys.argv
    use_equals = "--equals" in sys.argv
    use_gate = "--gate" in sys.argv
    cc_cfg = None
    if use_cc:
        cc_cfg = load_cc_switch()
        model = cc_cfg["model"]
        host = cc_cfg["source"]
        print(f"模型：{model}（{host}）")
    else:
        model = "qwen2.5:7b"
        host = "http://127.0.0.1:11434"
    sheets = [
        ("both_visible", [
            f"客户：{RECEIPT['customer_name']}",
            f"开票金额：{RECEIPT['invoiced']}",
            f"已入账金额：{RECEIPT['collected']}",
        ]),
        ("collected_only", [
            f"客户：{RECEIPT['customer_name']}",
            f"已入账金额：{RECEIPT['collected']}",
        ]),
        ("field_named", [
            f"已入账金额：{RECEIPT['collected']}",
        ]),
    ]
    if use_gate:
        sheets = [item for item in sheets if item[0] == "both_visible"]
    rows = []
    for name, lines in sheets:
        prompt = llm_prompt(lines, use_equals, use_gate)
        if use_cc:
            text = call_cc_switch(prompt, cc_cfg).strip()
        else:
            text = call_ollama(prompt, model, host).strip()
        status, detail = judge_llm_script(text)
        rows.append({"arm": name, "status": status, "detail": detail, "script": text})
        print(f"## {name}")
        print(f"  {status:10} {text}")
        print(f"  {detail}")
        print()
    out = {
        "model": model,
        "source": host if use_cc else "ollama",
        "temperature": 0,
        "thinking": "disabled" if use_cc else None,
        "n": 1,
        "equals_sentence": EQUALS_SENTENCE if use_equals else "",
        "gate_sentence": GATE_SENTENCE if use_gate else "",
        "ontology_sentence": ONTOLOGY_SENTENCE,
        "receipt": RECEIPT,
        "rows": rows,
    }
    tag = "gate" if use_gate else ("equals" if use_equals else "claim")
    slug = f"collection-ontology-gate-llm-{'cc-' if use_cc else ''}{tag}"
    dest = Path(__file__).parent / "results-v2" / f"{slug}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"结果：{dest}")


if __name__ == "__main__":
    if "--llm" in sys.argv or "--cc-switch" in sys.argv or "--gate" in sys.argv:
        run_llm()
    else:
        main()
