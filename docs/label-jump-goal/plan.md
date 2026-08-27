# plan：标注页"跳到进球"导航（label-jump-goal）

1. `gen_label_page.py`：模板加按钮 `跳到进球 (G)`；JS 加 `jumpGoal()`——当前位之后首个 `marks[key].r === "goal"`，无则从头找（循环）；**两次都落空（全批无 goal 标记）时 `show(cur)` 原地不动，与 jumpUnmarked 模式一致**。注意 jumpGoal 取 `mark()` 标注后前进同款**循环语义**（反复按 G 逐个过进球），与 jumpUnmarked 的"全列首个"不同，属刻意差异勿当 bug 改回；keydown 绑 `g`；帮助 small 行补 G（E501 余量充足，低危）
2. `tests/test_gen_label_page.py`：加 goal-anchor 同风格断言（按钮/jumpGoal/g 绑定/r==="goal" 条件）
3. 关口：ruff format + check --fix（复核 diff）+ pytest
4. 实测：20260822 review_batch1 页面按 G 循环跳 J 标事件
5. review01.md 存档；手册快捷键表补 G；commit

配套（一次性脚本，豁免 rules.md，不入库）：`work/_chk/patch_index_anchor_fields.py`——复刻 main 的 fid 排序与 cluster_candidates 聚类（确定性），为 20260822 review_batch1 的 events_index.json 补 `clip_src_start`（clip_window，**round 0.1s 与 main 同口径**）与 `continued`（plan_clip_segments，仅 ffprobe 不重剪片段）。**硬断言护栏**：先回放全量事件，断言回放 key 集合与旧 events_index key 集合**完全相等**（无缺失/无多余/数量一致），不等则打印差异并**中止不写回**（备份都还没动，天然安全）；写回用原子写；打印 continued=true 事件清单供立哥对照片段抽查（素材流动可能使续接判定与当初烘焙不符）。随后 gen_label_page 重生成 label.html（LSKEY 不变，localStorage 进度无损）。
