# Plan: 认人提效——轨迹选帧多裁 + CLIP 聚类逐人确认

## Overview

按 spec（docs/scorer-cluster/spec.md）实施。三个改动点按依赖排序：
多裁（数据源）→ 聚类（消费多裁）→ 页面（消费聚类）。每步独立可验。

## Architecture Decisions

- **球为聚类单位**：同球多裁 embedding 取均值，避免同球散簇；簇只服务
  预填分组，终裁仍是立哥
- **IoU 链选帧复用现有 mot_cache persons**：不引入新跟踪器（Bytetrack 等），
  帧间 IoU≥0.3 即链上，简单可测；链断即停，不脑补
- **质量分 = 面积 × 清晰度**：两个因子都可解释、可单测；不引入人脸朝向
  检测（依赖重、收益待证）
- **聚类不定簇数**：AgglomerativeClustering(distance_threshold)，
  阈值实跑标定；比 KMeans 省一个"先知道多少人"的悖论
- **页面改动最小化**：簇区是纯前端分组，导出仍走现有 roster 合并逻辑，
  roster schema 零改动

## Task List

### Phase 1: 多裁（crop_scorers.py）

- [ ] Task 1: 人框 IoU 链 `trace_person(persons, seed_frame, seed_box)` →
  窗口内该人 (frame_idx, box) 序列
- [ ] Task 2: 质量选帧 `rank_crops(链序列, framesdir)` → top N（≥0.5s 去重）
  + `_process_goal` 接多裁（--best-crops，默认 3；crops/crop_scores 落 entry）
- [ ] Task 3: 单测（IoU 链/质量排序/去重/旧数据兼容）+ 质量门

### Checkpoint 1

- [ ] ruff+pytest 全绿；对 scorers_b3 实跑一遍多裁，抽 5 球目检裁图质量；
  **提交 Phase 1**

### Phase 2: 聚类（cluster_scorers.py 新建）

- [ ] Task 4: embedding 提取 + 缓存（clip_cache.json，key=model+裁图 md5）
  + Schema 校验
- [ ] Task 5: 凝聚聚类 + scorer_clusters.json 落盘（--candidates 重复传参
  合并三批次）+ --evaluate 纯度报告（只统计 roster assignments 的键）
- [ ] Task 6: 单测（合成 embedding 聚类/缓存幂等/schema 拒坏数据）+ 质量门

### Checkpoint 2

- [ ] 实跑 20260722 三批次合并 --evaluate：簇数/纯度记录 review01，
  阈值标定（最多 3 档 0.20/0.25/0.30；缓存不含 threshold，调档不重复推理）；
  三档均不达标走降级出口（指标记 review、功能照上、纯度转观察值）；
  **提交 Phase 2**

### Phase 3: 页面（gen_scorer_page.py）

- [ ] Task 7: build_entries 接 --clusters（条目加 cluster_id）+ 簇区渲染
  （代表图墙 + 簇级选人 + 逐球覆盖）
- [ ] Task 8: 单测（簇合并 assignments/覆盖优先级/无 --clusters 兼容）+ 质量门

### Checkpoint 3

- [ ] 生成实页目检；四件套补齐（review01 存档实跑数据）；**提交 Phase 3**

## Risks and Mitigations

| 风险 | 影响 | 缓解 |
|------|------|------|
| CLIP 权重下载失败（代理） | 聚类不可跑 | 首跑验证；失败则报立哥手动放权重 |
| 同队撞脸并簇（纯度不达标） | 预填误导 | 逐球覆盖兜底；阈值下调；review 记录真实纯度 |
| IoU 链链错人（贴身对抗） | 裁错人 | 链长过短/框跳变过大即弃帧；crops[0]=质量最佳帧不保证是定位帧，由页面预览片段视频终裁兜底 |
| 帧图解码慢（多裁读图多） | 耗时 | 只解码链上帧；100 球 × ~20 帧 ≈ 分钟级，可接受 |

## Open Questions

- threshold 标定值（→ review01 记录）
