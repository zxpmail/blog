# 知乎总结文配图方案

风格:纯白手绘 | 小黑 IP | 16:9 | 少量红橙蓝中文批注

---

## 图1:Agent = Model + Harness

**位置:** 第一节开头(公式出现后)

**结构类型:** 概念隐喻

**核心意思:** 模型是引擎提供动力,Harness 是车身做控制——小黑是坐在驾驶舱里的系统工程师。

**画面:**
- 画面中央一辆极简手绘小车(一辆怪诞的敞篷车,只有底盘+轮子+方向盘)
- 车头位置一个黑盒,标红字"引擎 = 模型"(engine = model)
- 车身外壳(方向盘/刹车/仪表盘)用橙色线框标出,蓝字标注"Harness = 车身"
- 小黑坐在驾驶位上,双手握方向盘,表情冷静认真
- 引擎在冒热气(运转中),小黑在控制方向

**元素:** 怪敞篷车 / 引擎黑盒 / 方向盘 / 小黑

**中文标注:**
- 红:引擎 = 模型
- 蓝:Harness = 车身
- 橙:(方向盘图标旁边)→ 方向

---

## 图2:三种人机协作模式(In/On/Out of the Loop)

**位置:** 第一节末尾,三模式描述后

**结构类型:** 角色状态(三格小漫画)

**核心意思:** 三种人在循环中的位置,小黑演示三种姿态。

**画面:**
- 从左到右三个独立小场景,中间用橙色箭头隔开

**左格(循环外 Out):** 小黑背对着一台正在疯狂运转的机器(机器自己写代码、自己编译、自己输出),小黑坐在远处喝茶,地上堆满歪歪扭扭的代码文件。红线标注"失控←"。

**中格(循环内 In):** 小黑爬进机器内部,逐行盯着文件看,身体被机器齿轮夹住,满头汗。蓝字"瓶颈"。

**右格(循环上 On):** 小黑站在机器顶上,手里拿着扳手和设计图,机器正常运转,输出口排出整齐的文件。橙字标记"人在循环上"。

**元素:** 机器/茶/齿轮/扳手/设计图

**中文标注:**
- 红:失控
- 蓝:瓶颈(人在循环内)
- 橙:人在循环上

---

## 图3:Phase Gate 假阳——鸭子/句号/TODO 全放行

**位置:** 实验三之后

**结构类型:** Workflow 流程

**核心意思:** Phase Gate 只检查"动作发生了"(exit 0/文件存在),不检查内容对不对——鸭子、句号、TODO 全部绿灯放行。

**画面:**
- 左侧:小黑推着一辆手推车,车上堆着"鸭"、"。"、"TODO"、"0 passed"等奇怪物件
- 中央:一个怪诞的"门"(Phase Gate),门上只有一个传感器在读"文件存在=True""exit 0=True",没有读内容的装置
- 门上的信号灯显示绿色大勾
- 右侧:所有奇怪物件顺利通过,小黑一脸困惑地看着它们
- 门上方用红线写一个大大的"?"——门不读内容

**元素:** 手推车/门/信号灯/鸭子/句号/TODO

**中文标注:**
- 红:门不读内容
- 橙:exit 0 ✅ / 文件存在 ✅
- 蓝:(小黑头顶)内容呢?

---

## 图4:强模型质检是权衡——两端翘翘板

**位置:** 实验五之后(三档权衡)

**结构类型:** 概念隐喻

**核心意思:** 模型越强假阳越低,但误杀合法产品同步暴涨——precision-recall 是翘翘板。

**画面:**
- 一个手绘的翘翘板
- 翘翘板左边堆着"垃圾"标签的纸箱(假阳),右边堆着"合法产物"标签的文件(误杀)
- 小黑站在翘翘板中间,一只手按住左边(垃圾压下去了),右边弹起老高,文件散落一地
- 翘翘板底座标着"模型大小 → 越来越强"
- 小黑表情无奈——按得住一边,另一边就弹起来

**元素:** 翘翘板/纸箱/文件/小黑

**中文标注:**
- 红:(散落的文件上面)75% 误杀
- 蓝:(左边压住的纸箱)0% 假阳
- 橙:(底座)模型变大→

---

## 图5:Harness 边界——符号 vs 语义

**位置:** "Harness 的边界"章节

**结构类型:** 系统局部

**核心意思:** Harness 能兜住符号层(文件/exit code/格式),兜不住语义层(意图/内容质量/语义陷阱)——两者之间有一道鸿沟。

**画面:**
- 画面中央一道明显的断裂线(地面裂缝),将画面分成左右两半
- **左边(符号层):** 小黑站在坚实的地面上,手里稳稳接住文件、exit code 0、格式检查单等符号物件。地面写着"符号层 → 兜得住"。
- **右边(语义层):** 一个"G4 零用例"从裂缝中滑走,小黑伸手去捞但捞不到,手在半空中悬着。还有一些模糊的抽象形状(语义/意图/内容质量)从裂缝边缘飘走。
- 裂缝边缘用红线标注"语义鸿沟"

**元素:** 裂缝/文件/exit code 牌/抽象形状/小黑伸手

**中文标注:**
- 蓝:(左边)符号层 → 代码可验证
- 红:(裂缝上)语义鸿沟
- 橙:(右边漂浮的抽象形)语义陷阱 / 意图识别 / 内容质量
- 黑:(小黑表情旁)够不着…

---

## 生成方式

每张图单独用以下 prompt 模板生成:

```
Generate one standalone 16:9 horizontal Chinese article illustration.

Visual DNA:
Pure white background. Minimalist black hand-drawn line art. Slightly wobbly pen lines. Lots of empty white space. Sparse red/orange/blue handwritten Chinese annotations. Clean absurd product-sketch feeling. No gradients, no shadows, no paper texture, no complex background.

Recurring IP character:
小黑, a small solid-black absurd creature with white dot eyes, tiny thin legs, blank expression, slightly uneven hand-drawn body shape. 小黑 must perform the core action.

Theme: 对应图中{主题}
Structure type: 对应图中{类型}
Core idea: {核心意思}
Composition: {具体画面描述}

Chinese handwritten labels:
{标注词列表}

Color rules:
Black for main line art. Orange for flow/path. Red for warnings/problems. Blue for secondary notes.

Constraints:
One image, one core structure. Main subject 40-60% canvas. At least 35% white space. Max 5-8 short Chinese labels. No title in top-left corner. No formal diagram feel.
```

建议用 Midjourney 或 DALL-E,一次生成一张,不要拼图。
