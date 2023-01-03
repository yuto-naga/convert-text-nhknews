import itertools
import logging
import os
import re
import time
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# NHK BASE URL
NHK_BASE_URL = "https://www3.nhk.or.jp"

# NHKアクセスランキングURL
NHK_ACCESS_RANKING_URL = NHK_BASE_URL + "/news/ranking/access.html"

# 記事タイトルから取得しないワードのリスト
NOT_INTEREST_WORDS = ["駅伝"]

# Output
OUTPUT_DIRECTORY = "outputs"
LOG_DIRECTORY = "logs"


# 句読点があったら改行する
def convert_punctuation(value):
    return re.sub('([、。])', '\\1\n', value)


# ログの初期化
def log_init():
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(levelname)s:%(name)s - %(message)s",
                        filename=f"logs/log_{datetime.now():%Y%m}.log")


# タイトルに興味のないワードが含んでいるか
def is_include_not_interest(anchor):
    return any(not_interest_word in anchor.find("em").text for not_interest_word in NOT_INTEREST_WORDS)


# NHKのアクセスランキングからURLを取得する
def get_urls():
    logging.info("NHKアクセスランキングから記事URLを取得します")
    driver.get(NHK_ACCESS_RANKING_URL)
    # 定義した上条件で待機する(最大20秒)
    wait = WebDriverWait(driver, 20)
    # NAMEで指定したページ上の要素が読み込まれるまで待機
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "em")))
    html = driver.page_source.encode('UTF-8')
    soup = BeautifulSoup(html, "html.parser")

    # アクセスランキングの範囲を対象に抽出
    section = soup.find("section", class_="content--items")
    # アクセスランキングのaタグを抽出
    anchor_list = section.find_all("a")

    # フィルタしながらURL部分を抽出
    return map(lambda anchor: NHK_BASE_URL + anchor.get("href"),
               itertools.filterfalse(is_include_not_interest, anchor_list))


# 記事内容を取得する
def get_article(target_url):
    logging.info("記事内容を取得します 記事URL: " + target_url)
    # 連続してアクセスするので間隔を空ける
    time.sleep(3)

    # 結果を格納する記事内容
    contexts = []

    driver.get(target_url)
    # 定義した上条件で待機する(最大10秒)
    try:
        wait = WebDriverWait(driver, 10)
        # 指定したページ上の要素が読み込まれるまで待機
        wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
            and
            (EC.presence_of_element_located((By.CLASS_NAME, "content--summary"))
             or
             EC.presence_of_element_located((By.CLASS_NAME, "body-title"))
             )
        )
    except TimeoutException:
        logging.warning("指定した要素が取得できませんでした。該当の記事URLの取得を中止します。URL: " + target_url)
        return []

    # HTMLを文字コードをUTF-8に変換してから取得します。
    html = driver.page_source.encode('UTF-8')

    # htmlをBeutifulSoapで扱う
    soup = BeautifulSoup(html, "html.parser")

    # タイトルを抽出
    contexts.append("~~タイトル~~")
    contexts.append(re.sub('\n', '', soup.find("h1").text))

    # サマリを抽出
    contexts.append("~~要約~~")
    summary_contents = soup.find_all(class_=["content--summary", "content--summary-more"])
    for summary in summary_contents:
        contexts.append(convert_punctuation(summary.text))

    # 本文を抽出
    contexts.append("~~内容~~")
    detail_contents = soup.find_all(class_=["body-title", "body-text"])
    for detail_content in detail_contents:
        match detail_content['class']:
            case ["body-title"]:
                contexts.append(convert_punctuation(detail_content.text))
            case ["body-text"]:
                contexts.append(convert_punctuation(detail_content.text))

    return contexts


# テキストファイル化
def convert_text(news_list):
    logging.info("記事をテキストファイルに変換します")
    date = datetime.now().strftime('%Y_%m_%d_%H_%M')

    # 「outputs」ディレクトリ作成(すでにあってもOK)
    os.makedirs(OUTPUT_DIRECTORY, exist_ok=True)

    # テキストファイルを出力する
    path_w = OUTPUT_DIRECTORY + '/NHKニュース_' + date + '.txt'

    # 書き込み(新規作成のみ)
    try:
        # with-as文をつかうことで、ファイルのcloseする必要がなくなる
        with open(path_w, mode='x') as f:
            f.write('\n'.join(news_list))
    except FileExistsError:
        print("#すでにファイルが存在しています。: " + path_w)
        pass


# ログ初期化
log_init()
logging.info("**NHKニュースサイトから取得開始します**")

try:
    # Chromeのオプションを設定する
    options = webdriver.ChromeOptions()
    # 画面を描画しない
    options.add_argument('--headless')

    # Selenium Server に接続する
    driver = webdriver.Remote(
        command_executor='http://127.0.0.1:4444/wd/hub',
        options=options,
    )

    # アクセスランキングの記事URL一覧を取得
    url_list = get_urls()

    # 記事一覧URLから記事内容を取得してリストに格納
    news_list = []
    for index, url in enumerate(url_list):
        news_list.append(str(index + 1) + "番目のニュースです。")
        news_list.extend(get_article(url))

    # テキストファイル化
    convert_text(news_list)

except Exception as e:
    logging.error(f'caught {type(e)}: {str(e)}')
finally:
    logging.info("**NHKニュースサイトから取得終了します**")
    # ブラウザを終了する
    driver.quit()