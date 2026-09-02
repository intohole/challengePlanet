---
id: bp-minideploy-master-api
title: miniDeploy跨节点update-code标准调用路径(songguokr:8900)
summary: master=minideploy-cool@songguokr:8900, token取cluster_token.conf, 回环POST /api/cluster/apps/{name}/update-code+X-Service-Token; 应用实际运行节点用systemctl is-active判断, challengePlanet在edge-03
type: bestpractice
project: challengePlanet
date: 2026-08-27
tags: [bestpractice, pattern]
scope: project
related: []
---

# miniDeploy跨节点update-code标准调用路径(songguokr:8900)

## 场景
需要通过 miniDeploy 触发线上应用 git pull 更新代码(update-code)或重启时，不确定 master 在哪、API 怎么调。

## 做法
1. 找 master：master 是 minideploy-cool.service，在 songguokr(101.35.207.47) 上，监听 0.0.0.0:8900（ps 验证: uvicorn app.main:app --port 8900）。songguokr 上另有 9527 端口是别的服务，只有27条 openapi 路径，不是 miniDeploy。
2. 取 token：ssh songguokr 后读 /etc/systemd/system/minideploy-cool.service.d/cluster_token.conf 中 Environment=CLUSTER_TOKEN=<值>。
3. 跨节点更新应用：ssh songguokr 本机回环调 POST http://127.0.0.1:8900/api/cluster/apps/<app名>/update-code，Header X-Service-Token=<token>，返回 {"success":true,"message":"systemctl restart <app>.service 成功"}。update-code 支持 commit_id body 参数指定版本。
4. 判断应用在哪台跑：分别在三节点 systemctl is-active <app>.service；如 challengePlanet 实际运行在 edge-03(49.235.41.234)，songguokr/god 上是 inactive——master 会自动转发 worker，不要被本机 inactive 误导以为部署失败。

## 原因
/api/cluster/apps/{name}/{action} 挂在 /api 前缀下(app/api/__init__.py include cluster_router)，agent 瘦身版不暴露控制面路由。

## 反例
直接 https://songguokr.com/api/... 从外网调会 404/未登录；跨节点 HTTP 必须带 Host 头匹配 nginx server_name(songguokr.com)，本机回环调用则不需要。
