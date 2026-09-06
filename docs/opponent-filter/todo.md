# Todo: opponent-filter

- [x] T1 roster 伪球员 + build --all 跳过对手——commit dc92027 + 663ed2b，审查 Approved（偏离裁决：--all 按 team==对手队名全跳，符合"默认零对手"意图）
- [x] T2 确认页"标为对手"（逐球+整簇+分组+导出）——commit ea0de8f，审查 Approved（主会话实施：伪球员恒注入 PLAYERS/OPP_TAG 特判两端同步/oppmark 按钮+unassign/导出零引用剔除）
- [x] T3 GUI 出合集步"出我方合集"默认按钮——commit f3f847a，审查 Approved（主按钮 --team=team_config.team_name，无 roster 禁用提示；--all/高级选项保留）
- [x] T4 端到端实证——合成现场（非第六人正式数据）：--all 只出我方两产物、时长核对精确（6.02s=仅我方一球）、双 WARNING 过滤对手个人+分队、显式 --team 通道保留
- [ ] T5 立哥实机验证（重打 dist 后在第六人场次真实认人+出我方合集）

> 实施备注：T2 起因子代理周配额中断，由主会话亲自实施 + 独立审查员审查。
> T2 审查观察项（非阻断，留立哥实测定夺）：对手归属沿轨迹传播（同 track 自动标对手）；
> 伪球员在 PLAYERS 末尾，数字键 9 可能顺手标对手；roster 未 confirmed 时出合集落入自动模式（既有口径）。
