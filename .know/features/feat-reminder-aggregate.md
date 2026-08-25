# 打卡提醒按用户聚合去重触达

## 需求
每日 20:00 打卡提醒此前每个未打卡挑战各发一条，用户多挑战=消息轰炸；且无落地链接。

## 方案
`reminder_service.send_checkin_reminders` 把未打卡挑战按 user_id 分组，每用户合并为一条：
- 多个 → 标题「N 个挑战待打卡」，文案提示打断优先级；单个 → 标题保留挑战名。
- 发送补 `link=/challengePlanet/` 与 `data.challenge_count`。
- 已打卡 / 已结束（status≠active）不计入。
- 保持 `channels=["in_app"]`，email 通道待打通邮箱边界后追加。

## 验证
`tests/test_reminder_aggregation.py` 2/2 通过：聚合去重 + 跳过已打卡/已结束。

## 遗留
- email 触达待打通邮箱获取通道（见 adr-notify-email-channel-boundary）。
- notifyCenter 用户偏好（opt_in/静默时段）发送链路未消费，暂不依赖。