# -*- coding: utf-8 -*-
from app import create_app, mongo
from config import Config

if __name__ == '__main__':
    app = create_app(Config)

    # doc = mongo.db.auth.find_one({'app_id': '15a17561e-9ff1-4ee2-8cd9-5ec11fa2e375'})
    # print(doc)
    # 新开一个线程
    # 1. 从OneDrive获取数据并储存
    # 2. 开始刮削

    app.run()
