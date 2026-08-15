# Todo: 认人页簇合并 + 折叠

## Task 1: 页面态层 + 组解析工具函数

- [x] 写失败测试 TestBuildHtmlClusterMerge.test_cluster_state_layer_present
- [x] 跑测试确认失败
- [x] 模板插入 clState/saveClState/groupIdOf/computeGroups/groupTag
- [x] 改造 clusterAssign（按组作用 + 记 clAssign）
- [x] show() 逐球区簇号改显示组 id
- [x] 测试通过 + 质量门全绿
- [x] Commit

## Task 2: renderClusters 按组渲染 + 拆开

- [x] 加失败断言 test_group_render_and_split_present
- [x] 跑测试确认失败
- [x] 整段替换 renderClusters + 新增 groupLabel/splitGroup
- [x] 测试通过 + 质量门全绿
- [x] Commit

## Task 3: 拖拽合并 mergeInto + 预填跟随

- [x] 加失败断言 test_drag_merge_present
- [x] 跑测试确认失败
- [x] CSS 加 .drop-target / 拖拽光标
- [x] 新增 mergeInto（预填跟随 / clAssign 清除 / 同组与环防御 / PICKER-HOOK 埋点）
- [x] renderClusters 行加 draggable + drop 事件
- [x] 测试通过 + 质量门全绿
- [x] Commit

## Task 4: 合并弹条就地选人 + 数字键屏蔽

（9 条 ↔ plan 10 步：plan 的 Step 4 变量声明+新函数合并为一条，映射无遗漏）

- [x] 加失败断言 test_merge_picker_present
- [x] 跑测试确认失败
- [x] CSS 加 .picker
- [x] 新增 pickerGid/openPicker/closePicker；mergeInto 尾部挂 openPicker(dstGid)
- [x] renderClusters 加弹条渲染块
- [x] keydown 加弹条屏蔽段（Esc 关、1-9/E 屏蔽）
- [x] document click 弹条外关闭
- [x] 测试通过 + 质量门全绿
- [x] Commit

## Task 5: 折叠

- [x] 加失败断言 test_collapse_present
- [x] 跑测试确认失败
- [x] CSS 加 collapsed/foldbtn
- [x] 新增 collapseAll/isCollapsed/toggleCollapse
- [x] renderClusters 三处改造（总开关行 / 折叠态分支+折叠钮 / 图墙首图+按钮守卫）
- [x] 测试通过 + 质量门全绿
- [x] Commit

## Task 6: 实跑验证 + 手册同步 + 收尾

- [ ] 20260805_车百鼎 批次1 实数据生成页面（带 --clusters）
- [ ] 无 --clusters 兼容性回归（const CLUSTERS = []; 簇区隐藏）
- [ ] 手工验证清单交付立哥过浏览器（spec 11 条）
- [ ] 使用手册.html 认人节补簇合并/折叠/弹条说明 + spec-reviewer 审
- [ ] 本 todo 勾完 + 质量门终跑 + Commit
