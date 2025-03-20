# main.py 主逻辑：包括字段拼接、模拟请求
import hashlib
import logging
import random
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from functools import wraps

import requests

from config import READ_NUM, cookies, data, headers
from push import push

# 配置初始headers、cookies
session = requests.Session()
session.headers.update(headers)
session.cookies.update(cookies)
# 配置日志格式
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)-8s - %(message)s')

# 加密盐及其它默认值
KEY = "3c5c8717f3daf09iop3423zafeqoi"
COOKIE_DATA = {"rq": "%2Fweb%2Fbook%2Fread"}
READ_URL = "https://weread.qq.com/web/book/read"
RENEW_URL = "https://weread.qq.com/web/login/renewal"
READDATA_URL = "https://i.weread.qq.com/readdata/detail"


def encode_data(data):
    """数据编码"""
    return '&'.join(f"{k}={urllib.parse.quote(str(data[k]), safe='')}" for k in sorted(data.keys()))


def cal_hash(input_string):
    """计算哈希值"""
    _7032f5 = 0x15051505
    _cc1055 = _7032f5
    length = len(input_string)
    _19094e = length - 1

    while _19094e > 0:
        _7032f5 = 0x7fffffff & (_7032f5 ^ ord(
            input_string[_19094e]) << (length - _19094e) % 30)
        _cc1055 = 0x7fffffff & (_cc1055 ^ ord(
            input_string[_19094e - 1]) << _19094e % 30)
        _19094e -= 2

    return hex(_7032f5 + _cc1055)[2:].lower()


def renew(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is not None:
            return result
        # 刷新cookie
        logging.warning("❌ cookie 已过期，尝试刷新...")
        response = session.post(RENEW_URL, json=COOKIE_DATA)
        if 'succ' not in response.json():
            ERROR_CODE = "❌ 无法获取新密钥或者WXREAD_CURL_BASH配置有误，终止运行。"
            logging.error(ERROR_CODE)
            push(ERROR_CODE)
            raise Exception(ERROR_CODE)
        result = func(*args, **kwargs)
        if result is None:
            ERROR_CODE = "❌ 刷新登录配置后仍无法正常运行，终止运行。"
            logging.error(ERROR_CODE)
            push(ERROR_CODE)
            raise Exception(ERROR_CODE)

    return wrapper


@renew
def get_readdata():
    """获取当日阅读时长，以分钟计"""
    response = session.get(READDATA_URL, params={
        'mode': 'weekly'
    })
    readTimes = response.json().get('readTimes', None)
    if readTimes is None:
        return None
    today = datetime.now(timezone(timedelta(hours=8))).replace(
        hour=0, minute=0,
        second=0, microsecond=0
    )
    readTime_today = readTimes.get(str(int(today.timestamp())), 0)
    return readTime_today // 60


@renew
def read():
    data['ct'] = int(time.time())
    data['ts'] = int(time.time() * 1000)
    data['rn'] = random.randint(0, 1000)
    data['sg'] = hashlib.sha256(
        f"{data['ts']}{data['rn']}{KEY}".encode()).hexdigest()
    data.pop('s', None)
    data['s'] = cal_hash(encode_data(data))

    response = session.post(READ_URL, json=data)
    if 'succ' in response.json():
        return True
    return None


def main():
    readTime = get_readdata()
    logging.info(f"今日已阅读{readTime}分钟")
    remain = READ_NUM - readTime*2
    if remain <= 0:
        logging.info("毋需继续阅读，停止运行")
        return
    logging.info(f"还需要阅读{remain/2}分钟")
    for i in range(remain):
        logging.info(f"⏱️ 尝试第 {i+1} 次阅读...")
        read()
        time.sleep(30)
        logging.info(f"✅ 阅读成功，阅读进度：{readTime+(i+1)/2} 分钟")

    logging.info("🎉 阅读脚本已完成！")
    message = f"🎉 微信读书自动阅读完成！\n⏱️ "
    if readTime != 0:
        message += f'个人阅读时长：{readTime}分钟，'
    message += f'自动阅读时长：{remain / 2}分钟。'
    push(message)


main()
