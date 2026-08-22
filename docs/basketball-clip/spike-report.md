# Spike 报告：Python 3.10 + PyInstaller 打包可行性（SP-1/SP-2，2026-08-22）

> 对应 plan.md SP 阶段、spec.md O6。结论：**可行（PASS）**，O6 决策闭环。

## 结论

**Python 3.10.11 + PyInstaller 6.22.2 可以完整打包 basketball-clip 的全量依赖链**，
打出的 one-folder 包在干净目录实跑通过全部 import + torch 实算（`SPIKE-PASS`）。
打包方案正式落地，E 阶段按本报告的 collect-all 清单实施，无需降级方案。

## 环境

- Python 3.10.11（winget 用户级安装，`py -3.10` 可用；与现有 3.14 并存不冲突）
- venv：`C:\Code\basketball_clip\.venv-spike`（保留，E 阶段继续用）
- 依赖版本存档：`C:\Code\basketball_clip\packaging\spike\pip-list-spike.txt`
- torch 走 CPU 轮索引（`--index-url https://download.pytorch.org/whl/cpu`），
  装到 `torch 2.13.0+cpu`，避开 PyPI 的 CUDA 捆绑包（省 2GB+）

## 验证记录

1. **venv 内自测** `hello.py`（9 库 import + torch matmul）：全 OK，`SPIKE-PASS`。
2. **PyInstaller onedir 打包 + 干净目录实跑**：exe 自带解释器，与系统 Python 无关，
   全 OK，`SPIKE-PASS`（本机仍有 Python，真正零环境终验在 E 阶段干净 Windows 做）。

## 踩坑清单（核心产出）

PyInstaller 默认收集**收不全以下库**（症状：exe 内 `ModuleNotFoundError`），
必须逐个 `--collect-all`：

```
--collect-all cv2          # opencv 5.0 新版布局
--collect-all ultralytics  # 模型 YAML 配置
--collect-all open_clip    # 模型配置 JSON
--collect-all timm
--collect-all sklearn      # sklearn 1.7
--collect-all scipy
--collect-all uvicorn
--collect-all PIL
```

torch / numpy / fastapi **默认收集即通过**，无需额外参数。
工作 spec 文件留存：`C:\Code\basketball_clip\packaging\spike\spike-hello.spec`。

## 体积

- 最小 import 链包：**967MB**（collect-all 粗放口径，含全部子模块/数据文件）。
- 正式打包可裁剪（exclude 测试/文档子模块）；叠加双 YOLO(~150MB)、CLIP(~350MB)、
  ffmpeg(~80MB）后与 spec 预估的 1.5GB 量级吻合。

## 对 plan 的影响

- E-1 的 PyInstaller spec 以上述 collect-all 清单为基线。
- 打包机已就绪：3.10 解释器 + venv 现成，E 阶段直接复用。
- 打包耗时参考：每轮全量打包约 3–5 分钟（本机）。
