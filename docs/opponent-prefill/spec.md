# Spec: 对手自动预填（opponent-prefill）

> 2026-09-07 立哥立项："对手为什么不能自动标记？球衣颜色不同"。opponent-filter 的增量。
> 代码改动在新仓库 `C:\Code\basketball_clip`。

## Objective

认人确认页上，球衣颜色识别为**黑色**（team_guess="黑"）的进球自动给出**"对手预填"**建议，
配"接受全部对手预填"一键全收——对手标注从逐球点击变为一眼确认 + 一键。

**红线**：预填只是建议，人终裁（项目既定"机器排序+人裁判"哲学；颜色识别有误判率，
全自动标死会无声污染合集）。白队/便服/无颜色数据不做任何对手预填。

## 设计

1. **预填规则**：条目 `team_guess == "黑"` → 视为对手预填候选（JS 侧判定，数据源
   scorer_candidates 既有 team_guess，crop_scorers 零改动）。`"白"`（我方色系）/
   `"便服"`（不定）/null → 不预填。
   注：teamOfTag 的阵营映射含"蓝→OPP"，但 `team_guess` 取值空间只有（黑/白/便服），
   不会出现"蓝"，故本功能只处理"黑"，不与蓝映射冲突。
2. **页面呈现**：候选球进度行显示"对手预填：黑"（与"颜色预填"提示共存时以对手预填为准，
   避免双提示）；预填不写入 marks（与号码预填同口径：未接受前不算归属）。
3. **逐球接受**：候选球"标为对手"按钮文案变"接受对手预填"（同一 assign(OPP_TAG) 路径）；
   非候选球的"标为对手"按钮行为不变（opponent-filter T2 原样）。
4. **一键全收**：按钮区加"接受全部对手预填"（沿用 acceptAllPrefills 的批量口径：
   只写未 touched 的候选球，不碰已归属/已手改/哨兵球），点击后统计提示。
5. **预填状态持久**：无新增 localStorage 键（acceptAll 后落 marks，沿用现有持久化）。

## Commands

```powershell
C:\Code\basketball_clip\.venv-spike\Scripts\python.exe -m pytest -q
python -m ruff format scripts tests gui; python -m ruff check --fix scripts tests gui
```

## Project Structure / Style / Boundaries

- `scripts/gen_scorer_page.py`（唯一改动点）+ `tests/test_gen_scorer_page.py`
- 沿用 acceptAllPrefills 批量模式与 OPP_TAG 特判（T2 已落地）；scripts 其他文件零改动
- Never：预填直接写 marks（绕过人工）；改 team_guess 上游产出

## Testing Strategy

- JS 契约断言（沿用现有模式）：黑球出"对手预填"提示、白/便服/null 不出、
  逐球接受路径、acceptAll 只写未 touched 候选、不碰哨兵/已归属
- node --check 语法守卫；pytest/ruff 全绿，存量不破

## Success Criteria

1. team_guess="黑" 的球显示对手预填，其余不出现
2. "接受全部对手预填"一键批量归属，已手改/已归属/哨兵球不受影响
3. 全程预填未接受前不进 marks（导出 roster 不含未确认预填）

## Open Questions

- O1：未来若场次我方穿深色（黑=我方），规则需按场次我方色系反转——本期不做，
  team_config 若加 my_color 字段再说（报告备注即可）
