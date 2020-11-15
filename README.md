# One App API

将 Onedrive 数据缓存到本地

## 环境

- `python` >= 3.8
- `mongodb`

## 步骤

安装

```bash
pip3 install -r requirements.txt
```

安装 `docker-mongo` (可选)

- [安装和设置步骤](./docker-mongo.md)
- 修改 `config.py` 中的 `MONGO_URI` 来正确连接 `mongodb` 服务

`gunicorn` 部署

```bash
gunicorn --threads 3 -b 127.0.0.1:5000 run:app
```

## 其他

后台管理密码会随机生成，项目目录下的 `config.ini`。修改后重启应用生效
