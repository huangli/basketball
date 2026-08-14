# spec：认人确认页导出文件名即 roster.json

日期：2026-08-14 · 提出：立哥（"认人分簇导出是不是有同样问题"——是）

## 背景与目标

与 label-export-batch 同类问题：确认页 scorer.html 导出恒为
`roster_<场次>.json`，而 CLI（video people 预填链 / build）只认
`work/<场次>/roster.json`，人工改名是多余环节且会改错。
页面按钮文案本来就写"导出 roster.json"，实际下载名却带场次后缀——自相矛盾。

目标：导出文件名直接就是 `roster.json`，下载后移动到 `work/<场次>/` 即可。

## 边界

- 只改导出下载名与相关文案；payload schema（session/confirmed/players/assignments）
  与 confirmed 判定契约不动
- roster 无批次概念（逐批确认时每批页面导出的都是累计全量，经 --roster-existing
  预填链合并），故无需批次号、无需 run_session/video.py 传参
- 多批次页面先后导出会同名，浏览器自动加 ` (1)` 后缀——移动时去掉即可（手册提醒）

## 方案

`gen_scorer_page.py` 三处文案 + 一处下载名：`a.download = "roster.json"`（常量，
不注入）；按钮文案已是"导出 roster.json"不动；按键提示行、alert、模块 docstring
同步。无新增参数。

## 成功标准

- 任一确认页导出文件名为 `roster.json`，移到 `work/<场次>/` 后
  `video people` 下一批预填与 `video build` 直接认
- 全量 pytest 绿；ruff 干净

## 联动更新

- `使用手册.html` §一第 3 步：改名 → 移动
- `使用手册.html` §五 FAQ「build 报 roster 不存在」：补"旧版页面导出的
  roster_<场次>.json 需先改名"
