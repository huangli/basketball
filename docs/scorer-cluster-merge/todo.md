# Todo: 认人页簇合并 + 折叠

## Task 1: 页面态层 + 组解析工具函数

- [ ] 写失败测试 TestBuildHtmlClusterMerge.test_cluster_state_layer_present
- [ ] 跑测试确认失败
- [ ] 模板插入 clState/saveClState/groupIdOf/computeGroups/groupTag
- [ ] 改造 clusterAssign（按组作用 + 记 clAssign）
- [ ] show() 逐球区簇号改显示组 id
- [ ] 测试通过 + 质量门全绿
- [ ] Commit

## Task 2: renderClusters 按组渲染 + 拆开

- [ ] 加失败断言 test_group_render_and_split_present
- [ ] 跑测试确认失败
- [ ] 整段替换 renderClusters + 新增 groupLabel/splitGroup
- [ ] 测试通过 + 质量门全绿
- [ ] Commit

## Task 3: 拖拽合并 mergeInto + 预填跟随

- [ ] 加失败断言 test_drag_merge_present
- [ ] 跑测试确认失败
- [ ] CSS 加 .drop-target / 拖拽光标
- [ ] 新增 mergeInto（预填跟随 / clAssign 清除 / 同组与环防御 / PICKER-HOOK 埋点）
- [ ] renderClusters 行加 draggable + drop 事件
- [ ] 测试通过 + 质量门全绿
- [ ] Commit

## Task 4: 合并弹条就地选人 + 数字键屏蔽

（9 条 ↔ plan 10 步：plan 的 Step 4 变量声明+新函数合并为一条，映射无遗漏）

- [ ] 加失败断言 test_merge_picker_present
- [ ] 跑测试确认失败
- [ ] CSS 加 .picker
- [ ] 新增 pickerGid/openPicker/closePicker；mergeInto 尾部挂 openPicker(dstGid)
- [ ] renderClusters 加弹条渲染块
- [ ] keydown 加弹条屏蔽段（Esc 关、1-9/E 屏蔽）
- [ ] document click 弹条外关闭
- [ ] 测试通过 + 质量门全绿
- [ ] Commit

## Task 5: 折叠

- [ ] 加失败断言 test_collapse_present
- [ ] 跑测试确认失败
- [ ] CSS 加 collapsed/foldbtn
- [ ] 新增 collapseAll/isCollapsed/toggleCollapse
- [ ] renderClusters 三处改造（总开关行 / 折叠态分支+折叠钮 / 图墙首图+按钮守卫）
- [ ] 测试通过 + 质量门全绿
- [ ] Commit

## Task 6: 实跑验证 + 手册同步 + 收尾

- [ ] 20260805_车百鼎 批次1 实数据生成页面（带 --clusters）
- [ ] 无 --clusters 兼容性回归（const CLUSTERS = []; 簇区隐藏）
- [ ] 手工验证清单交付立哥过浏览器（spec 11 条）
- [ ] 使用手册.html 认人节补簇合并/折叠/弹条说明 + spec-reviewer 审
- [ ] 本 todo 勾完 + 质量门终跑 + Commit
