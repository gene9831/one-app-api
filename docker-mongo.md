# docker mongo

安装

```bash
docker pull mongo:latest
```

查看本地镜像

```bash
docker images
```

运行容器

```bash
docker run -itd --name mongo -p 27017:27017 mongo --auth
```

> :warning:公网下谨慎放通数据库端口

进入容器

```bash
docker exec -it mongo mongo admin
```

创建管理员用户

```bash
> db.createUser({ user:'admin',pwd:'123456',roles:[ { role:'userAdminAnyDatabase', db: 'admin'},"readWriteAnyDatabase"]});
Successfully added user: {
    "user" : "admin",
    "roles" : [
        {
            "role" : "userAdminAnyDatabase",
            "db" : "admin"
        },
        "readWriteAnyDatabase"
    ]
}
> db.auth('admin', '123456')
1
```

验证成功后携带 admin 身份切换到其他数据库，为其他数据库创建用户

```bash
> use one_app
switched to db one_app
> db.createUser({ user:'one', pwd:'oneapp', roles:[ { role:'readWrite', db:'one_app' }]})
Successfully added user: {
    "user" : "one",
    "roles" : [
        {
            "role" : "readWrite",
            "db" : "one_app"
        }
    ]
}
```

切换到 admin 库, 看一下我们创建的用户

```bash
> use admin
switched to db admin
> db.system.users.find({ user: 'one' }).pretty()
{
    "_id" : "one_app.one",
    "userId" : UUID("5885cced-67c0-4cca-816c-6250071f6626"),
    "user" : "one",
    "db" : "one_app",
    "credentials" : {
        ......
    },
    "roles" : [
        {
            "role" : "readWrite",
            "db" : "one_app"
        }
    ]
}
```

退出后清除之前的授权，再重新进入。授权返回 1 则成功

```bash
docker exec -it mongo mongo one_app
> db
one_app
> db.auth('one','oneapp')
1
```
