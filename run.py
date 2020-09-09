# -*- coding: utf-8 -*-
from app import create_app
from config import Config

if __name__ == '__main__':
    app = create_app(Config)

    # 新开一个线程
    # 1. 从OneDrive获取数据并储存
    # 2. 开始刮削

    app.run(debug=True)
