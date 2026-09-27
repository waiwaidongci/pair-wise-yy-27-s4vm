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
- 锁定段落由负责人执行，锁定后任何新修订都会被拒绝。

## 审定记录

- 有版本编辑权限的人可以送审版本异文，负责人可代编辑送审；同一条异文只能有一条待审记录。
- 具备项目 `review` 权限的审阅人查看原句、对齐句、拟句与理由后选择 `approved`（通过）或 `returned`（退回），两种结论都必须写明意见。
- 退回的改动需先修订异文才能再次送审；通过后内容即为该版本的定本，定本异文不能再修改。
- 段落锁定前，所有异文都必须有带意见的通过记录；缺意见、仍在待审、被退回或送审被撤回时都不能锁定。
- 负责人可以撤回尚未审阅的送审，撤回后需重新送审。
- 项目页按待审（`pending`）、退回（`returned`）、已通过（`approved`）分组列出记录，并附 `withdrawn`（已撤回）分组。

## 审定接口

- `POST /api/variants/{id}/reviews`：送审异文（`user_id`）
- `POST /api/reviews/{id}/decision`：审定（`user_id`、`action=approved|returned`、`comment`）
- `POST /api/reviews/{id}/withdraw`：负责人撤回待审送审
- `GET /api/works/{id}/reviews?user_id=...`：按状态分组列出审定记录

## 主要接口

- `POST /api/users`、`POST /api/works`
- `POST /api/works/{id}/witnesses`、`POST /api/witnesses/{id}/editors`
- `POST /api/works/{id}/passages`、`POST /api/works/{id}/access`
- `POST /api/alignments`
- `POST /api/variants`、`POST /api/variants/{id}/revisions`
- `GET /api/passages/{id}/snapshots/{revision}?user_id=...`
- `POST /api/passages/{id}/lock`
- `GET /api/works/{id}/collation?user_id=...`

导出接口把版本对齐、异文、注释、残损缺口和锁定状态组合成可复核的校勘稿。
