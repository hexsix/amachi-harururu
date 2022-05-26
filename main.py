"""
filename: main.py
author: hexsix <hexsixology@gmail.com>
date: 2022/05/26
description: 
"""

import json
import logging
import os
import time
from typing import Any, Dict, List

import feedparser
import httpx


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger()


RSS_URL = os.environ['RSS_URL']
TG_TOKEN = os.environ['TG_TOKEN']


def download() -> Dict:
    logger.info('Downloading RSS ...')
    rss_json = None
    for retry in range(3):
        logger.info(f'The {retry + 1}th attempt, 3 attempts in total.')
        try:
            with httpx.Client() as client:
                response = client.get(RSS_URL, timeout=10.0)
            rss_json = feedparser.parse(response.text)
            if rss_json:
                break
        except:
            logger.info('Failed, next attempt will start soon.')
            time.sleep(6)
    if not rss_json:
        raise Exception('Failed to download RSS.')
    logger.info('Succeed to download RSS.\n')
    return rss_json


def parse(rss_json: Dict) -> List[Dict[str, Any]]:
    logger.info('Parsing RSS ...')
    items = []
    for entry in rss_json['entries']:
        try:
            item = dict()

            items.append(item)
        except Exception as e:
            logger.info(f'Exception: {e}')
            continue
    logger.info(
        f"Parse RSS End. {len(items)}/{len(rss_json['entries'])} Succeed.\n")
    return items


def send(chat_id: str, photo: str, caption: str, rj_code: str) -> bool:
    logger.info(f'Send rj code: {rj_code} ...')
    target = f"https://api.telegram.org/bot{TG_TOKEN}/sendPhoto"
    params = {
        'chat_id': chat_id,
        'photo': photo,
        'caption': caption
    }
    try:
        with httpx.Client() as client:
            response = client.post(target, params=params)
        if response.json()['ok']:
            logger.info(f'Succeed to send {rj_code}.')
            return True
        else:
            logger.warn(f'Telegram api returns {response.json()}')
            logger.warn(f'photo: {photo}, caption: {caption}')
    except Exception as e:
        logger.error(f'Exception: {e}')
        pass
    logger.error(f'Failed to send {rj_code}.\n')
    return False


if __name__ == '__main__':
    rss_json = download()
    json.dump(rss_json, open("sample.json", 'w', encoding='utf8'),
              ensure_ascii=False, indent=4)
    logging.info(str(rss_json))
