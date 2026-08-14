# spec：标注页导出文件名自动带批次号

日期：2026-08-14 · 提出：立哥（"导出的时候要自动带上 batch1,batch2 更好"）

## 背景与目标

现状：label.html 导出恒为 `goals_<场次>.json`，立哥须人工改名为 `goals_batchK.json`
放回 `work/<场次>/`，CLI（video people/build）才认。2026-08-14 车百鼎场次实踩：
立哥改成 `goals_20260805_车百鼎1.json`（缺 batch 字样），discover_batches 跳过
全部 3 个文件，people 报错"下无 goals.json / goals_batchK.json"。

目标：标注页导出文件名直接就是 `goals_batchK.json`，下载后只需移动、无需改名，
从根上消除改错名的可能。

## 边界

- 只改导出文件名生成逻辑与 run_session ⑦ 的传参；导出 payload schema 不变
  （`{"session", "goals"}` 契约不动）
- 旧布局（`review/` 无批次号、`--batch` 不传）保持旧文件名 `goals_<场次>.json`，
  向后兼容；adhoc 模式同旧布局处理
- 下载文件仍需人工移动到 `work/<场次>/`（浏览器下载目录不可控，不在本期范围）

## 方案

- `gen_label_page.py` 新增 `--batch K`（int，可选）：传了 → 导出 `goals_batchK.json`；
  不传 → 维持 `goals_<场次>.json`。页面按钮/提示文案同步显示真实文件名
- `run_session.py` ⑦ 命令对 batchK 批次传 `--batch K`；adhoc 不传
- 批次号由编排层显式注入，不做从 --index 路径猜批次之类的隐式推导（rules.md 鲁棒条）

## 成功标准

- `video score` 跑出的 label.html 导出文件名即 `goals_batchK.json`，移动到
  `work/<场次>/` 后 `video people --batch K` 直接认
- 不传 --batch 的手工调用行为不变（旧文件名）
- 全量 pytest 绿；ruff 干净

## 联动更新

- `使用手册.html` §一第 2 步改名说明改为"移动即可"（AGENTS.md：CLI 行为变更同步手册）
- `docs/video-cli/spec.md` §45"改名是人工步骤"口径更新为"导出已带批次名，仅需移动"
