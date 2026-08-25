# 通知中心 email 触达的渠道与权限边界

## 背景
打卡提醒等召回场景需要真实触达，站内信对离开用户无效，需叠加 email 渠道。notifyCenter 平台已支持。

## 边界事实
- `POST /api/notify/send` 支持 `channels=["in_app","email","webhook"]`。
- email 收件地址必须由调用方通过 `data.email` 主动传；`email_channel.send()` 只读 `notification["data"]["email"]`，不会按 user_id 反查用户中心。
- 用户中心 `GET /api/users/{id}` 需 `user.read`（管理端）权限，service token 默认拿不到，无法据此批量取用户邮箱。
- email 是否发出取决于 notifyCenter 侧 `SMTP_HOST` 是否配置（`EmailChannel.enabled = email.enabled and smtp_host`）。

## 决策
调用侧用 nexus.notify 客户端传 `channels` + `data.email`；无法确认邮箱时降级为仅 in_app，不破坏现有。附带 `/challengePlanet/` 落地链接与 `challenge_count` 元数据。

## 影响
后续如需邮件召回，须先打通「服务端按 user_id 取邮箱」通道（新增只读接口或本地缓存邮箱）与渠道偏好控制。