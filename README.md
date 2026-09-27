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
- 有版本编辑权限的人可以把异文送审，负责人可代送（`on_behalf_of`）；同一异文同时只能有一条待审记录，待审中的异文不能修改。
- 有审阅权限（`review`）的用户或负责人看过原句、拟句和理由后选择通过或退回，必须写明意见；退回的改动须修订产生新层后才能再送。
- 通过且与当前层一致的异文即为该版本的定本（导出中以 `is_definitive` 标出）。
- 段落锁定前必须至少有一条通过的审定，且不存在待审记录或缺意见的记录；锁定后任何新修订都会被拒绝。
- 负责人可以撤回尚未审阅的送审；项目页按待审、退回、已通过分组列出审定记录。

## 主要接口

- `POST /api/users`、`POST /api/works`
- `POST /api/works/{id}/witnesses`、`POST /api/witnesses/{id}/editors`
- `POST /api/works/{id}/passages`、`POST /api/works/{id}/access`
- `POST /api/alignments`
- `POST /api/variants`、`POST /api/variants/{id}/revisions`
- `POST /api/reviews`、`POST /api/reviews/{id}/decision`、`POST /api/reviews/{id}/withdraw`
- `GET /api/works/{id}/reviews?user_id=...`
- `GET /api/passages/{id}/snapshots/{revision}?user_id=...`
- `POST /api/passages/{id}/lock`
- `GET /api/works/{id}/collation?user_id=...`

导出接口把版本对齐、异文、注释、残损缺口和锁定状态组合成可复核的校勘稿。
