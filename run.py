# -*- coding: utf-8 -*-
from app import create_app, mongo
from config import Config

if __name__ == '__main__':

    app = create_app(Config)
    print(Config.POJ_DIR)

    res = mongo.db.driveItem.find({'test': {'$exists': True}})
    for r in res:
        print(123)
    # 新开一个线程
    # 1. 从OneDrive获取数据并储存
    # 2. 开始刮削

    # app.run(debug=True)
