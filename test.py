# -*- coding: utf-8 -*-

import threading
import time

t = None


def hello():
    print(123)
    global t
    t = threading.Timer(1, hello)
    t.start()


if __name__ == '__main__':
    hello()
    time.sleep(3)
    if isinstance(t, threading.Timer):
        t.cancel()
    print('end')
