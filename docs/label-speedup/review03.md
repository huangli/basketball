# review03：倍速口径修正（验收后回改）

日期：2026-08-09　触发：立哥验收实操 + spec-reviewer 验收收尾审查建议项 1

## 问题

F2 初版按 spec 交付"页面默认 playbackRate = 2"。spec-reviewer 在验收收尾
审查中指出：审核片段本身已烘焙 2x（`gen_review_clips.py:63` SPEED=2.0，
setpts/atempo），页面再设 2x = **有效 4x**。spec 初版"现状：页面常速播放"
只看了页面层，没算片段层，属 spec 事实遗漏（review01/02 两轮均未发现，
审查盲区：两轮都核对了 CLIP_BEFORE_SEC 所在行区，但未顺查 SPEED 常量）。

## 处置

- 立哥拍板：页面默认 1x（= 有效 2x，其习惯档），S 键切页面 2x（= 有效 4x）
- 代码：`gen_label_page.py` show() 改 `v.playbackRate = 1` 并加注释说明
  两层倍速关系；`#speed` 按钮初值"倍速：1x"；S 键切换逻辑不变
- 测试：回归断言改 `playbackRate = 1`
- 文档：spec F2 节/成功标准 2/风险表、plan Step 1、todo Task 1 全部同步；
  AGENTS.md 工作流描述用有效速度口径

## 教训（写入记忆）

涉及"速度/时长/尺寸"类需求时，必须沿数据流查清**每一层**的变换
（素材帧率 → 片段烘焙 SPEED → 页面 playbackRate），只看一层必错。

## 关口复跑

改后 `ruff format` / `ruff check --fix` / `pytest -q` 全绿（274 passed）；
label.html 重新生成（session 20260722_3）+ `node --check` 通过；
立哥已知悉口径变化。review02 中"playbackRate=2"的对应表述以本文件为准。
