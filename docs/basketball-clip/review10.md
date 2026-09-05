# Review 10: spec O2/O5 更正审查（2026-09-05）

> 审查员：spec-reviewer 角色子代理（只读审查）。结论：修订后**通过**。

## 阻断问题与处置

- **Tech Stack Re-ID 行体积数字未同步**（350MB vs O5 已更正的 605MB）→ 已修：改为"体积见 O5"间接引用，消除重复维护点。

## 通过项

- O2 GPL 更正与新仓库 README/INSTALLER_LICENSE.txt 口径一致；GPL 合规表述准确（无 nonfree/许可文本随包/独立子进程不构成衍生作品）。
- 与豁免清单/Boundaries/Success Criteria 无矛盾。

## 背景记录（P0 热修）

立哥发布前实测炸出 `Unknown encoder 'libx264'`：BtbN LGPL build 编译时 `--disable-libx264 --disable-libx265`。热修 commit `6efdec2`（新仓）：ffmpeg 换 BtbN GPL build，fetch_assets 增加 `_verify_libx264` 强制闸（跳过路径也验证——正是"文件在就放行"的静默洞让事故溜进产物）。安装器重打 858MB，立哥第六人测试现场（work/ 14806 文件 3.1GB）备份回灌零损失。热修审查 clean。
