## 功能简介
- 定时查询 qBittorrent 中在下载和等待的慢任务，将其移动到最后，以便腾出下载任务。
- 支持 docker compose 部署
- qBittorrent（需启用 WebUI API Key 认证，≥5.2.0）
- 认证方式：**WebUI API Key**（不再使用用户名/密码）

## 版本与发布
版本唯一来源为 `qbslowqueue/__init__.py`，包含四个字段：
`__version__` / `__release_status__` / `__test_sequence__` / `__docker_tag__`。
Docker 镜像 tag、Compose 镜像名均由它派生，禁止在别处另设版本号。

当前为 **正式版 V1.2.0**（formal），`__test_sequence__` 归 0，镜像 tag 为干净标签（无 `-test.N` 标识）。
镜像地址：`docker.cnb.cool/1983shake/qb-slow-queue:latest`（由 `__init__.py` 派生）。

## 部署步骤
1. 在 qBittorrent **WebUI → 选项 → WebUI → 认证** 中生成 API Key（格式 `qbt_` 开头，共 32 字符）。
2. 拷贝 `docker-compose.yml`，下载 `sample.env` 并重命名为 `.env`，填入 `QB_HOST` / `QB_PORT` / `QB_API_KEY`。
3. 构建并启动（镜像 tag 自动从 `__init__.py` 派生）：
   - Linux / macOS：`bash build.sh`
   - Windows（PowerShell）：`pwsh build.ps1`
4. 查看日志：`docker logs qb-slow-queue`。

## .env 配置项
| 配置项 | 说明 | 默认值 |
|---|---|---|
| QB_HOST | qBittorrent 的 IP 地址 | 192.168.1.100 |
| QB_PORT | WebUI 端口 | 8080 |
| QB_API_KEY | WebUI API Key（**必填**） | - |
| SPEED_THRESHOLD | 速度阈值（字节/秒），0 表示仅移动无速度任务 | 51200 |
| CHECK_INTERVAL | 检查间隔（秒） | 300 |
| LOG_LEVEL | 日志级别: DEBUG/INFO/WARNING/ERROR | INFO |

## 交付前校验
```bash
python verify_release.py
```
校验 `__init__.py` ↔ `Dockerfile` ↔ `docker-compose.yml` 的版本一致性。
