# domain-manage

这个模块负责域名层事务。

当前职责：

- 根域名静态页
- 子域名入口组织
- Cloudflare DNS、Tunnel、Access、Pages、Worker 配置
- 域名层文档

这里维护根域名入口、子域名组织、Cloudflare 配置和静态页。应用自身的启动与公网接入脚本继续在对应子项目里维护。
