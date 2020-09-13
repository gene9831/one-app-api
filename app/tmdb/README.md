# TMDB API

> **注意：**
> 本文中提到的管理员指的是本项目搭建的服务的管理员

## 先决条件

1. 获取 TMDB API 读访问令牌。不是 API 密钥。类似这样的

```text
eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiI0MTc2NjY5NTdiZWQxNThkZDYyY2EzZjZiZWZlNDI5NCIsInN1YiI6IjVkOTUyNTc4MjljNjI2--------------------b3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.dYAzjnY74SzjHn----------
```

2. [更改 TMDB 配置](#更改配置)

## 电影数据

- 方法：`TMDB.getDataByItemId`
- 需要管理员：否
- 参数
  | 名称 | 必要 |
  | --- | --- |
  | `item_id` | 是 |
- 返回：`JSONObject`

请求

```http
POST /api/tmdb HTTP/1.1
Host: localhost:5000
Content-type: application/json

{
    "jsonrpc": "2.0",
    "method": "TMDB.getDataByItemId",
    "params": ["01ZAO4SQJ2UBJDI237LZGZKQF4HLAWX7MP"],
    "id": "1"
}
```

响应（部分）

```json
{
  "id": "1",
  "jsonrpc": "2.0",
  "result": {
    "adult": false,
    "backdrop_path": "/j29ekbcLpBvxnGk6LjdTc2EI5SA.jpg",
    "homepage": "http://movies.disney.com/inside-out",
    "id": 150540,
    "imdb_id": "tt2096673",
    "original_language": "en",
    "original_title": "Inside Out",
    "overview": "...",
    "popularity": 61.607,
    "poster_path": "/skleUgOto5JCY20cC8KALSEankA.jpg",
    "title": "头脑特工队"
  }
}
```

## 配置

### 获取配置

- 方法：`TMDB.getConfig`
- 需要管理员：是
- 参数：无
- 返回：`JSONObject`

请求

```http
POST /api/admin/tmdb HTTP/1.1
Host: localhost:5000
Content-type: application/json
X-Username: username
X-Password: secret

{
    "jsonrpc": "2.0",
    "method": "TMDB.getConfig",
    "params": [],
    "id": "1"
}
```

响应

```json
{
  "id": "1",
  "jsonrpc": "2.0",
  "result": {
    "Authorization": {
      "comment": "Bearer Token",
      "field": "headers",
      "secret": true,
      "type": "str",
      "value": "********"
    },
    "language": {
      "comment": "语言-地区",
      "field": "params",
      "secret": false,
      "type": "str",
      "value": "zh-cn"
    },
    "proxies": {
      "comment": "代理配置",
      "field": "",
      "secret": false,
      "type": "dict",
      "value": {}
    }
  }
}
```

每个配置项是由 ConfigItem 类生成的，是一个 `JSONObject`

ConfigItem

- `comment`: 字段说明
- `field`: session 参数位置
- `secret`: 是否敏感
- `type`: 类型
- `value`: 值

### 更改配置

- 方法：`TMDB.setConfig`
- 需要管理员：是
- 参数：一个 `JSONObject`
- 返回：`JSONObject`

请求

```http
POST /api/admin/tmdb HTTP/1.1
Host: localhost:5000
Content-type: application/json
X-Username: username
X-Password: secret

{
    "jsonrpc": "2.0",
    "method": "TMDB.setConfig",
    "params": [
        {
            "Authorization": {
                "value": "your token"
            },
            "language": {
                "comment": "语言",
                "value": "en-us"
            }
        }
    ],
    "id": "1"
}
```

响应

```json
{
  "id": "1",
  "jsonrpc": "2.0",
  "result": {
    "Authorization": {
      "value": 1
    },
    "language": {
      "comment": 1,
      "value": 1
    }
  }
}
```
