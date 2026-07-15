## 功能简介
- 定时查询qBittorrent中在下载和等待的慢任务，将其移动到最后，以便腾出下载任务。
- 支持docker compose部署
- qBittorrent V5.2.3

## 简要步骤：
1. 确认qBittorrent WebUI → 工具 → 选项 → 连接 → 勾选“启用队列”。
2. 拷贝docker-compose.yml或复制文件内容。
3. 下载sample.env并重命名.env。
4. 编辑.env文件内容。
5. 在docker容器内构建即可。