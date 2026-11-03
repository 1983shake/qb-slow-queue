# 变更记录（CHANGELOG）

本文件记录 qb-slow-queue 的每次变更。版本号唯一来源为 `qbslowqueue/__init__.py`。

## 记录规则

- 每次代码 / 配置 / 文档变更都记录在对应版本下。
- **测试版（test）是中间迭代过程**，不单独作为长期条目保留。
- **测试版转正式版时**：将该测试版期间的过程记录**整理总结**后并入对应正式版本的变更记录——只保留净结果（最终状态），去掉过程中的往返改动（如某功能先加后删）。
- 条目按「新增 / 变更 / 优化 / 移除」分类，时间倒序（最新版本在上）。

---

## [1.3.0] - 2026-11-03 - 正式版（formal）

> 本版由测试版 #3 转正而来。测试版 #2（持续慢速判定）、#3（合并参数、降消耗）的过程记录已整理并入本条，仅保留净结果。

### 新增
- **WebUI API Key 认证**：qBittorrent 连接改用 WebUI API Key（`qbt_` 前缀，32 字符）认证，替代用户名/密码。`qbittorrent-api>=2026.5.3`（该版本起支持 `api_key` 参数，最低 Python 3.10）。API Key 模式跳过 cookie 登录，请求走 `Authorization: Bearer`。
- **`__init__.py` 版本体系**：版本唯一来源 `qbslowqueue/__init__.py`（`__version__` / `__release_status__` / `__test_sequence__` / `__docker_tag__`），Docker tag、Compose 镜像名均由其派生。
- **构建脚本** `build.sh` / `build.ps1`：从 `__init__.py` 派生镜像 tag 并构建启动。
- **交付前校验** `verify_release.py`：校验 `__init__.py` ↔ `Dockerfile` ↔ `docker-compose.yml` 版本一致性。
- **国内 PyPI 镜像**：`Dockerfile` 内置腾讯云 + 清华 PyPI 镜像（`/etc/pip.conf`），规避构建网络无法直连 `pypi.org` 的问题。
- **README「运行逻辑」章节**：启动流程、单次扫描 Mermaid 流程图、判定与移动规则、定时循环。

### 变更
- **慢速判定为「即时移动」**：每次扫描时，凡是 `downloading` / `stalledDL` 状态且当前下载速度低于 `SPEED_THRESHOLD` 的任务，立即移至队列末尾等待。仅当存在 `queuedDL`（排队等待）任务时才执行调整。
- **`.env` 配置项**：`QB_API_KEY`（必填）、`SPEED_THRESHOLD`（默认 51200 字节/秒）、`CHECK_INTERVAL`（默认 300 秒）、`LOG_LEVEL`。
- **镜像地址**：`docker.cnb.cool/1983shake/qb-slow-queue:latest`（干净标签）。

### 优化（降低系统消耗）
- `Client` 启动时创建一次并**复用**整个生命周期，仅启动时做一次 `app.version` 探活，不再每轮重建连接 / 探活。
- 单次扫描仅发起**一次** `torrents_info` 请求，统计复用已获取列表，不二次全量拉取。
- 主循环用 `time.sleep(CHECK_INTERVAL)` 简单轮询，移除 `schedule` 调度库依赖（镜像更轻、无调度线程开销）。

### 移除
- 用户名 / 密码认证（`QB_USER` / `QB_PASS` / `auth_log_in`）。
- `SLOW_DURATION` 持续观察窗口判定（测试版 #2 引入、#3 合并进 `CHECK_INTERVAL`）。
- `schedule` 依赖。

### 过程记录（测试版 #2 → #3，已并入，仅留净结果）
- #2：引入 `SLOW_DURATION` 持续慢速判定 + `_slow_since` 计时，`sample.env` 全面加注释。
- #3：合并 `CHECK_INTERVAL` 与 `SLOW_DURATION`（删除后者），改为即时移动；删除 `_slow_since` 与二次 `torrents_info` 拉取；移除 `schedule`。
- 净结果即上方「即时移动 + 降低消耗」，`SLOW_DURATION` / `_slow_since` / `schedule` 均不保留。

---

## [1.2.0] - 2026-11-03 - 正式版（formal）

> 版本号从 1.0.0 直接升至 1.2.0（1.1.0 未发布）。本版无功能改动，仅版本号变更。

### 变更
- 版本号 `1.0.0` → `1.2.0`；镜像 tag 保持 `docker.cnb.cool/1983shake/qb-slow-queue:latest`。

---

## [1.0.0] - 2026-11-03 - 正式版（formal）

> 由测试版 #1 转正。测试版 #1 的过程记录已并入本条。

### 新增
- 项目初始交付：qBittorrent 慢速任务调度（定时把慢速下载任务移至队列末尾，为排队任务腾出带宽）。
- WebUI API Key 认证（替代用户名/密码）。
- `__init__.py` 版本体系、`build.sh` / `build.ps1`、`verify_release.py`。
- `sample.env` 配置模板、`Dockerfile`、`docker-compose.yml`、`README.md`。
- `.gitignore` 补充：忽略 `.workbuddy/`（Agent 本机工作态/记忆）、OS 临时文件、`*.bak` / `*~`。

### 变更
- 镜像地址定为 `docker.cnb.cool/1983shake/qb-slow-queue:latest`。

### 移除
- 用户名 / 密码认证。
