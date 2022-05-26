"""
filename: main.py
author: hexsix <hexsixology@gmail.com>
date: 2022/05/26
description: 
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List

from bs4 import BeautifulSoup
import feedparser
import httpx
import redis


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger()


RSS_URL = os.environ['RSS_URL']
TG_TOKEN = os.environ['TG_TOKEN']
REDIS = redis.from_url(os.environ['REDIS_URL'])
CONFIGS = json.load(open('configs.json', 'r', encoding='utf8'))


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
    filtered_cnt = 0
    for entry in rss_json['entries']:
        try:
            item = dict()
            if 'type_SOU' not in entry['summary']:
                filtered_cnt += 1
                continue
            soup = BeautifulSoup(entry['summary'], 'html.parser')
            """work_category
            <div class="work_category type_SOU">
                <a href="https://www.dlsite.com/maniax/fsr/=/work_type/SOU" target="_blank">
                    ボイス・ASMR
                </a>
            </div>
            """
            work_category = 'ボイス・ASMR'
            """img
            <img alt="オナサポ科のJK双子ママ♪～焦らしテクで快楽絶頂!～ [犬走り]" class="lazy" src="https://img.dlsite.jp/resize/images2/work/doujin/RJ392000/RJ391233_img_main_240x240.jpg"/>
            """
            # try:
            #     item['img_url'] = soup.select_one('img').attrs['src']
            # except KeyError:
            #     item['img_url'] = ''
            """work_name
            <dt class="work_name">
                <span class="period_date">
                    2022年06月22日 23時59分 割引終了
                </span>
                <div class="icon_wrap">
                    <span class="icon_lead_01 type_exclusive" title="DLsite専売">
                        DLsite専売
                    </span>
                </div>
                <a href="https://www.dlsite.com/maniax/work/=/product_id/RJ391233.html" target="_blank" title="オナサポ科のJK双子ママ♪～焦らしテクで快楽絶頂!～">
                    オナサポ科のJK双子ママ♪～焦らしテクで快楽絶頂!～
                </a>
            </dt>
            """
            item['work_name'] = soup.select_one(
                '.work_name').select_one('a').attrs['title']
            item['author'] = entry['author']
            item['tags'] = []
            for t in entry['tags']:
                tag = t['term']
                if '/' in tag:
                    tag = tag.replace('/', '/#')
                tag = '#' + tag
                item['tags'].append(tag)
            item['link'] = entry['link']
            item['rj_code'] = re.search(r'RJ\d*', entry['link']).group()
            items.append(item)
        except Exception as e:
            logger.info(f'Exception: {e}')
            continue
    logger.info(
        f"Parse RSS End. {len(items)}/{len(rss_json['entries'])} Succeed. {filtered_cnt} filtered by ASMR. Others failed.")
    return items


def send(chat_id: str, photo: str, caption: str, rj_code: str) -> bool:
    logger.info(f'Send rj code: {rj_code} ...')
    if photo:
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
    else:
        target = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        params = {
            'chat_id': chat_id,
            'parse_mode': 'MarkdownV2',
            'text': caption
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


def escape(text: str) -> str:
    escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for escape_char in escape_chars:
        text = text.replace(escape_char, '\\' + escape_char)
    return text


def construct_params(item: Dict):
    rj_code = item['rj_code']
    photo = ''
    caption = f'\\#{rj_code}\n' \
              f'*{escape(item["work_name"])}*\n' \
              f'\n' \
              f'{escape(item["author"])}\n' \
              f'\n' \
              f'{" ".join(escape(t) for t in item["tags"])}\n' \
              f'\n' \
              f'{item["link"]}'
    return photo, caption, rj_code


def filter(item: Dict) -> bool:
    if REDIS.exists(item['rj_code']):
        return True
    return False


def redis_set(rj_code: str) -> bool:
    for retry in range(5):
        logger.info(f'The {retry + 1}th attempt to set redis, 5 attempts in total.')
        try:
            if REDIS.set(rj_code, 'sent', ex=2678400):  # expire after a month
                logger.info(f'Succeed to set redis {rj_code}.\n')
                return True
        except Exception:
            logger.info('Failed to set redis, '
                        'the next attempt will start in 6 seconds.')
            time.sleep(6)
    logger.info(f'Failed to set redis, {rj_code} may be sent twice.\n')
    return False


def main() -> None:
    logger.info('============ App Start ============')
    rss_json = download()
    items = parse(rss_json)
    filtered_items = [item for item in items if not filter(item)]
    logger.info(f'{len(filtered_items)}/{len(items)} filtered by already sent.\n')
    for item in filtered_items:
        photo, caption, rj_code = construct_params(item)
        for rss_author in CONFIGS.keys():
            if rss_author in item['author']:
                if send(CONFIGS[rss_author], photo, caption, rj_code):
                    redis_set(rj_code)
                time.sleep(10)
    logger.info('============ App End ============')


if __name__ == '__main__':
    main()
