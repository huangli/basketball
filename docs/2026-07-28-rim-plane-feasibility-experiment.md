# rim-plane crossing 进球判定可行性实验（2026-07-28）

> 验证「球穿越篮筐平面（rim-plane crossing）」能否在现有素材（DJI Pocket 3 手持）
> 上自动区分真假进球。结论：**不可行**——5fps 与 30fps 两轮实验均无判别力，
> rim-plane 列入已证伪清单。本文记录调研依据、实验数据与根因。

## 1. 背景与目的

现有流水线（`docs/2026-07-26-current-goal-detection-pipeline.md`）的运动学候选
召回良好但精度低（review_v3：113 事件 / 71 分钟，精度约 22%）。精筛环节此前已证伪
多个方向：VLM 单图判定（任务形态错配）、筐 ROI 标定（v3 翻车）、背景热点过滤等。

本次聚焦一个尚未在本素材验证、但有外部成功先例的方向——**rim-plane crossing**：
不依赖看到「球进网瞬间」，而是检测「球在筐上方 → 球在筐下方」的状态跨越，把入网
遮挡盲区「包住」而非硬观测。目的是回答：**这个方法在 Pocket 3 手持素材上能不能
自动区分真假进球？**

## 2. 外部先例调研（arXiv + GitHub，2026-07-28）

调研脚本：`work/_research.py`、`work/_research2.py`（走本机 Clash 代理 7897）。

### 2.1 最接近的同场景项目：owengong/bball-highlights

- 需求几乎一致：「从两段半场野球视频自动生成进球集锦」。
- **最初用 color + motion（颜色+运动像素）原型**，后在 `NOTES.md` 记录废弃原因：
  1. *No ball, just pixels*——纯运动方案从不检测球，任何移动橙色区域（球衣/皮肤/
     平移时的地板）都算；干净的空心球穿白网时几乎无橙色像素，关键时刻信号消失。
  2. *Pixel-starved*——真实距离下穿网球仅 1~3 像素，在零噪声底上靠 ~1 vs ~3 像素
     判定。
  3. *Overfit filters*——10 个串行滤波器常数过拟合到特定时间戳。
- **改为 rim-plane crossing**：YOLO 检测球在「标定筐」附近，球从筐上方明确到下方
  （在筐 x 宽度内、下降足够快、短窗口不反弹回升）= 进球。原话：
  > This *brackets* the net-occlusion gap instead of fighting it.

### 2.2 主流方法归纳

所有公开成功案例判 made 的方法**只有一类**——球穿越筐平面 / 球与筐空间关系，
**全部依赖知道筐在哪**：

| 项目/论文 | 方法 | 筐依赖 |
|---|---|---|
| owengong/bball-highlights | rim-plane crossing（标定筐一次） | 是 |
| nitinhemaraj/Basketball-shot-detection | 球轨迹线性回归与筐相交 | 是 |
| sPappalard/SwishAI（97★） | YOLO 球+筐空间关系 | 是 |
| avishah3（267★） | YOLO 球+筐 | 是 |
| arXiv Fusing Motion Patterns | 「篮筐周围外观变化」检测得分 | 是（筐区域） |

**零个案例用「网抖动光流」独立判定进球。** 唯一沾边运动信号的 arXiv 论文用的是
「筐区域外观变化」（非网抖动），且为转播视角辅助信号。

## 3. 前提事实（用户确认）

- 拍摄设备：**DJI Pocket 3，手持，非固定机位**——筐在画面像素坐标里持续漂移。
- 进球时筐**基本在画面内**（手持晃动但未出画）——rim-plane 的参照系存在，但会移动。

## 4. 实验设计

两轮实验，对比「确认进球（正样本）」与「候选中未确认者（负样本）」的信号判别力。
判据：

- `crossing` = 最大无检测盲区后球的 y > 盲区前球的 y（下落穿越筐平面）。
- `falling` = 盲区前球 y 单调下降（抛物线下落逼近筐）。
- `straddle` = 窗口内球既出现在筐 `hoop_cy` 上方又下方。
- `blind` = 最大连续无检测盲区时长。
- `nball` = 窗口内检出「筐附近球」的帧数。

数据源：`work/20260722/candidates_yes.json`（25 个确认进球）、
`work/20260722/candidates_review_v3.json`（326 候选，取未确认者为负样本）。
筐参照 `cx/cy` 取自候选锚点位置（球进网瞬间≈筐，1920 宽坐标系）。

## 5. 实验 1：5fps 缓存分析

脚本 `test/analyze.py`，复用 `work/detect/{fid}_mot_cache.json`（5fps 全程球检测缓存），
锚点 ±2s 窗口，每帧取最高 conf 球。秒级完成。

```
POSITIVE(25): crossing=14/25 (56%)  straddle=24/25  cross&straddle=14/25
NEGATIVE(30): crossing=20/30 (67%)  straddle=25/30  cross&straddle=15/30
```

**无判别力**——负样本穿越率（67%）反高于正样本（56%）。根因：5fps 下盲区大多仅
0.2~0.6s，分不清真入网盲区与采样漏帧；每帧「最高 conf 球」常为不同球/假阳性，
before_y/after_y 近似随机。

## 6. 实验 2：30fps 高帧率验证

脚本 `test/rim_plane_hifi.py`、`test/summarize.py`。原片锚点 ±1.5s 按 30fps 抽帧
（`scale=1920:-2`），abdullahtarek 球检测（imgsz1280, conf0.15），每帧选「距筐
(cx,cy) 最近且半径 280px 内」的球。8 个确认进球 + 8 个候选。

```
POSITIVE(8): crossing=3/8 (37%)  falling=1/8  cross&fall=0/8  blind_avg=0.54s  nball=54/90
NEGATIVE(8): crossing=5/8 (62%)  falling=1/8  cross&fall=1/8  blind_avg=0.35s  nball=42/90
```

**高帧率仍无判别力**——负样本穿越率（62%）再次高于正样本（37%），falling 正负
均 1/8。原始轨迹数据存 `test/hifi_result.json`。

## 7. 结论与根因

**rim-plane crossing 在 Pocket 3 手持素材上不可行**，无论 5fps 还是 30fps。两个
具体原因：

1. **筐漂移导致固定坐标选球失准。** 手持 ±1.5s 内筐在像素坐标移动，用锚点那一刻的
   `cx/cy` 当固定参照选「筐附近球」，筐漂走后选到的是随机移动目标，穿越方向近似
   抛硬币。owengong 能用固定坐标，是因其固定机位、筐不动。
2. **检测器在筐附近不干净，盲区被假阳性填充。** 30fps 下 blind_avg 仅 0.35~0.54s
   （只有 1 样本出现 1.83s 大盲区），说明 abdullahtarek 在筐附近持续检出东西
   （网、球员橙色、晃动），把真正入网盲区填满——rim-plane 依赖的「球消失→重现」
   结构根本不形成。

### owengong 成功与本项目失败的差异

| 维度 | owengong | 本项目 |
|---|---|---|
| 机位 | 固定（Mac 架设） | Pocket 3 手持 |
| 筐 | 画面内不动 | 持续漂移 |
| 球检测器 | yolo11m COCO sports ball | abdullahtarek |
| 盲区 | 干净消失-重现 | 被假阳性填充 |

rim-plane 成立需两个前提——**筐稳定**与**检测器在筐附近干净**——本项目一个都不满足。

### 局限说明

- **样本量**：30fps 实验为探针性质，仅 8 个确认进球 + 8 个候选；5fps 实验 25+30。
  两轮方向一致（负样本穿越率均反高于正样本），结论方向性可信，但非全量统计置信。
- **负样本定义**：负样本取自 review_v3 中「未在 candidates_yes 确认」的候选，
  ≠ 确认假阳性——可能混入未标注的真进球（candidates_yes 仅 25 个，review_v3 有
  326 个），这会拉高负样本穿越率。但正样本率反低于负样本，说明无论负样本纯度如何
  信号都无判别力，结论不受影响。

## 8. 已证伪清单更新

加入 `current-goal-detection-pipeline.md` §5（勿再尝试）：

- **rim-plane crossing（5fps 与 30fps）**：Pocket 3 手持素材下无判别力。根因为筐漂移
  + 检测器在筐附近假阳性填充盲区。需「固定机位 + 筐逐帧跟踪 + 更干净球检测器」三者
  齐备才可能成立，单一投入无效。
- **网抖动光流**：零公开成功案例，最接近的同场景项目（owengong）明确废弃 motion
  方向。

至此自动化精筛全部方向均已证伪：VLM、网抖动、球轨迹速度签名、rim-plane——共同根因
是同一物理约束：**手持漂移 + 入网遮挡 + 检测器在筐附近不可靠**，使「进球那一刻」
在自动信号层面始终缺失或被噪声淹没。

## 9. 建议

- **现有素材（Pocket 3 手持）**：人工终判是唯一可靠出路。减负方向限于降低单候选
  查看成本（缩略图网格预筛明显废话 + label.html 批量否定），不含自动排序
  （无判别信号）。
- **采集端治本（推荐）**：下次拍摄用三脚架固定 Pocket 3 覆盖全场/单筐固定视角。
  筐不漂移后 rim-plane 才有物理基础——这是 owengong 跑通的核心条件，比任何算法
  投入都有效。

## 复现

- 5fps 分析：`python test/analyze.py`
- 30fps 实验：`python test/rim_plane_hifi.py`（后台约 15~25 分钟）→ `python test/summarize.py`
- 原始轨迹：`test/hifi_result.json`
- 外部调研：`python work/_research.py` / `work/_research2.py`（需本机代理 7897）
