# 数字人文文本校勘

这是一个 Python 标准库实现的校勘工作台，使用 SQLite 保存作品、版本、残片、转录、段落、异文、注释、修订层和快照，并通过 `http.server` 暴露 JSON API。

## 启动与测试

```bash
python app.py
python -m unittest discover -s tests -v
```

默认端口 `8114`，地址 <http://127.0.0.1:8114>。首次启动创建一个带缺页残片和不可辨标记的示例。数据库可通过 `COLLATION_DB` 指定，端口可通过 `PORT` 指定。

## 业务规则

- 版本类型限定为 `version`、`fragment`、`transcription`。
- 段落和版本必须属于同一作品，同一版本不能重复对齐同一段落。
- 只有负责人或被单独授权的编辑可以修改对应版本；其他用户只有查看权限。
- `[缺页]`、`[不可辨]`、`[残损]` 等标记会参与校勘稿导出和缺口统计，不匹配的方括号会拒绝保存。
- 每次新增或修改异文都会产生递增修订号和 JSON 快照；提交必须携带 `expected_revision`，旧页面不能覆盖新层。
- 拥有作品 `review` 权限的审阅人（或负责人）可对每条异文的**当前修订层**写下 `adopted`（采用）/`rejected`（驳回）结论和意见；同一层可改判，旧结论保留但置为失效。
- 同一条异文提交新修订层后，之前所有生效中的审阅结论自动失效（`superseded`），该异文回到未决状态，须重新审阅。
- 负责人锁稿前系统统计当前层尚无生效结论的异文：若有未决内容则拒绝锁定并提示数量。
- 锁定段落由负责人执行，锁定后任何新修订和新审阅都会被拒绝。

## 主要接口

- `POST /api/users`、`POST /api/works`
- `POST /api/works/{id}/witnesses`、`POST /api/witnesses/{id}/editors`
- `POST /api/works/{id}/passages`、`POST /api/works/{id}/access`
- `POST /api/alignments`
- `POST /api/variants`、`POST /api/variants/{id}/revisions`、`POST /api/variants/{id}/reviews`
- `GET /api/passages/{id}/snapshots/{revision}?user_id=...`
- `POST /api/passages/{id}/lock`
- `GET /api/works/{id}/collation?user_id=...`

导出接口把版本对齐、异文、注释、审阅结论、残损缺口和锁定状态组合成可复核的校勘稿：每条异文带 `decision`（`adopted`/`rejected`/`pending`）与中文 `decision_label`（采用/驳回/未决），并给出 `adopted_count`、`rejected_count`、`pending_count` 汇总及每个段落的 `pending_count`；失效结论保存在 `superseded_reviews` 中备查。
