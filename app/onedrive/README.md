# OneDrive API

## Login

> POST /login

| 参数         | 必要 |
| ------------ | ---- |
| app_id       | 是   |
| app_secret   | 是   |
| redirect_url | 是   |

返回 `sign_in_url` 和 `state`，请求 `sign_in_url` 后重定向到 `redirect_url`

## Login callback

> GET /callback

即 `redirect_url`。不需要手动请求

## Items

> GET /items

| 参数 | 必要 |
| ---- | ---- |
| path | 否   |

> PUT /items

全面更新 items

> PATCH /items

增量更新 items

> DELETE /items

| 参数   | 必要 |
| ------ | ---- |
| app_id | 否   |

删除所有 items 或者指定 app_id 的部分 items

## Drives

> GET /drives
