# Spec: 素材目录跨启动记忆（gui-state-persist）

> 2026-09-07 立哥实测反馈："为什么每次 exe 打开，选素材都要重新填"。

## Objective

GUI 向导记住素材目录：扫描成功后持久化，下次启动/新建场次自动预填；续接已有场次时
预填该场次的素材目录（读 video_cli.json 的 srcdir）。

## 设计（已落地，commit b877cf6 + 6d29fa9）

- 后端：scan 成功即原子写 `work/.gui/state.json`（tmp + 回读校验 + os.replace）；
  `GET /api/gui-state` 返回 last_srcdir；status 响应新增 srcdir 字段
- 降级口径：状态文件缺失=正常空态静默；损坏 → null + WARNING（不 500）
- 前端：输入框 input 事件实时同步 state.srcdir；异步预填仅在 state.srcdir 为空时生效
  （防冲掉用户手输）；续接场次同理只在用户未输入时预填
- 失败留痕：前端拉取失败 console.warn；后端损坏 WARNING；caplog 断言锁定

## Testing

tests/gui/test_app.py 新增 5 用例（持久化往返/空态/损坏降级/状态含 srcdir/无状态 null）。
pytest 1139 全绿，ruff 全绿。
