# -*- coding: utf-8 -*-

import argparse
import hashlib
import json
import os
import pickle
import queue
import re
import threading
import time
from collections import defaultdict

import jieba
import jieba.analyse
from bookmarks_converter import BookmarksConverter
from bs4 import BeautifulSoup as bf

from parallel_download import ParallelDownload

cluster_result = {}


def get_bookmarks_from_export(bookmark_content):
    """
    """
    relink = '<A HREF="(\S*)"\s.*>(.*)</A>'
    bookmarks = re.findall(relink, bookmark_content)
    raw_result = []
    for item in bookmarks:
        bm_info = list(item)
        bm_info.append("")
        bm_info.append(0)
        raw_result.append(bm_info)
    return raw_result


def get_bookmarks_from_folder(bookmark_content):
    """
    """
    json_result = json.loads(bookmark_content)
    bookmark_info = apart_dict(json_result, "type", 'url')
    raw_result = []
    for item in bookmark_info:
        bm_info = list()
        bm_info.append(item['url'])
        bm_info.append(item['name'])
        bm_info.append(item)
        bm_info.append(0)
        raw_result.append(bm_info)
    return raw_result


def collect_page_content(bookmarks, data_path, args):
    """
    """
    proxies = {}
    if args.proxy:
        proxies["http"] = args.proxy
        proxies["https"] = args.proxy
    in_queue = queue.Queue()

    for i, bookmark in enumerate(bookmarks):
        file_name_md5 = string_md5("*****".join(bookmark[0:2]))
        file_path = data_path + '/' + file_name_md5
        # 如果已经下载了页面，就直接加载结果
        if os.path.isfile(file_path):
            load_success = True
            temp_file = open(file_path, 'rb')
            try:
                bookmarks[i] = pickle.load(temp_file)
            except EOFError:
                load_success = False
            if args.advance and bookmarks[i][3] != 0:
                load_success = False
            if load_success:
                continue

        # chrome 内部url和本地文件直接聚一类，不参与计算了
        if bookmark[0].startswith("chrome:") or bookmark[0].startswith("file:"):
            bookmarks[i][3] = -1
            temp_file = open(file_path, 'wb')
            ss = pickle.dump(bookmarks[i], temp_file)
            continue

        in_queue.put((i, bookmark))

    out_queue = queue.Queue()
    for i in range(int(in_queue.qsize() / 10) + 1):
        downloader = ParallelDownload("downloader" + str(i), in_queue, out_queue)
        downloader.daemon = True
        downloader.start()

    while in_queue.qsize() > 0:
        print("There are currently {0} threads being fetched".format(threading.active_count() - 1))
        time.sleep(4)

    while out_queue.qsize() > 0:
        item = out_queue.get()
        serial_num = item[0]
        if item[1]:
            bookmarks[serial_num][3] = 0
            bookmarks[serial_num].append(item[1])
        else:
            bookmarks[serial_num][3] = -2
            # 结果保存到文件夹中
        file_name_md5 = string_md5("*****".join(bookmarks[serial_num][0:2]))
        file_path = data_path + '/' + file_name_md5
        temp_file = open(file_path, 'wb')
        pickle.dump(bookmarks[serial_num], temp_file)
    return bookmarks


def add_tags(bookmarks, topK=20):
    """
    """
    for i, bookmark in enumerate(bookmarks):
        if bookmark[3] == 0 and len(bookmark) >= 5:
            content = bookmark[5]
            bookmark_tag_word = jieba.analyse.textrank(content, topK, withWeight=False, allowPOS=('ns', 'n', 'vn', 'v'))
            if len(bookmark_tag_word) == 0:
                bookmark_tag_word = jieba.analyse.extract_tags(content, topK)
            bookmarks[i].append(bookmark_tag_word)
            print('add_tags {}'.format(i))

    return bookmarks


def extract_text(bookmarks):
    """
    """
    for i, bookmark in enumerate(bookmarks):
        if bookmark[3] == 0 and len(bookmark) >= 4:
            try:
                if bookmark[4]:
                    bsoup = bf(bookmark[4], "html5lib")
                    # 过滤掉页面中的js和css
                    for script in bsoup(["script", "style"]):
                        script.extract()

                    bookmark_text = " ".join(bsoup.stripped_strings)
                    bookmarks[i].append(bookmark_text)
                    print('extract_text 处理第{}个'.format(str(i)))
            except IndexError:
                print('Index Error in extract', len(bookmark), bookmark)
                pass
    return bookmarks


def unvlaid_data(x):
    """
    切词前过滤掉无效字段,这里仅过滤了纯数字
    """
    return not x.isdigit()


def cut_word(bookmarks_result):
    """
    对文章进行切词
    """
    bookmark_corpus = list()
    map_dict = dict()
    index = 0
    for i, bookmark in enumerate(bookmarks_result):
        try:
            if bookmark[3] >= 0:
                map_dict[index] = i
                seg_list = jieba.cut(bookmark[5], cut_all=True)
                bookmark_corpus.append("  ".join(filter(unvlaid_data, seg_list)))
                index += 1
        except IndexError:
            print('IndexError in cut_word', len(bookmark), map_dict)
    print("抽取到有效文章%d" % len(bookmark_corpus))
    return map_dict, bookmark_corpus


def extract_features(bookmark_corpus, debug_mode=False):
    """
    抽取特征
    """
    from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
    transformer = TfidfTransformer(smooth_idf=False)
    # 最大选10000个词作为特征词
    vectorizer = CountVectorizer(min_df=1, max_features=10000)

    # 不限制特征词数量
    # vectorizer = CountVectorizer(min_df=1)

    # word bag 特征向量
    # feature_matrix = vectorizer.fit_transform(bookmark_corpus)

    # tf-idf 特征向量
    feature_matrix = transformer.fit_transform(vectorizer.fit_transform(bookmark_corpus))

    print("计算完成文章的特征向量")
    return feature_matrix


def hierarchical_clustering(feature_matrix, kvalue, debug_mode=False):
    """
    层次聚类
    """
    from sklearn.cluster import AgglomerativeClustering
    clustering = AgglomerativeClustering(linkage='ward', n_clusters=kvalue).fit(feature_matrix.toarray())
    clustering_result = clustering.labels_
    if debug_mode:
        print("hierarchical_clustering result:")
        print("------------------------------------------------------------------------------------")
        print(clustering_result)
    return clustering_result


def kmeans_clustering(feature_matrix, kvalue, debug_mode=False):
    """
    kmeans-聚类
    """
    from sklearn.cluster import KMeans
    kmeans = KMeans(n_clusters=kvalue, random_state=0).fit(feature_matrix)
    clustering_result = kmeans.labels_
    if debug_mode:
        print("kmeans_clustering result:")
        print("------------------------------------------------------------------------------------")
        print(clustering_result)
    return clustering_result


def calu_cluster_name(cluster_content, key, topK=3):
    """
    计算簇的特征词
    :param cluster_content:
    :param key:
    :param topK:
    :return:
    """
    if key == "-1":
        return u"local file"
    if key == "-2":
        return u"cann't open page"
    content = cluster_content.get(key, "")
    full_content = " ".join(content)
    tag_words = jieba.analyse.extract_tags(full_content, topK, allowPOS=('ns', 'n', 'vn', 'v'))
    if len(tag_words) == 0:
        tag_words = jieba.analyse.extract_tags(full_content, topK)

    return "-".join(tag_words)


def write_mark(bookmarks_result, clustering_result, map_dict):
    """
    将聚簇结果标记写入数据
    :param bookmarks_result:
    :param clustering_result:
    :param map_dict:
    :return:
    """
    for index, label in enumerate(clustering_result):
        bookmark_index = map_dict[index]
        bookmarks_result[bookmark_index][3] = label
        result = defaultdict(list)
        cluster_content = defaultdict(list)
        for item in bookmarks_result:
            key = str(item[3])
            result[key].append(item[1])
            if int(item[3]) >= 0 and len(item) >= 5:
                cluster_content[key].append(item[5].lower())

    return result, cluster_content


def print_result(result, cluster_content):
    """
    打印结果
    :param result:
    :param cluster_content:
    :return:
    """
    for k, v in result.items():
        print(k, calu_cluster_name(cluster_content, k))
        print("/*************************************************************************************/")
        for value in v:
            print(value)
        print("/*************************************************************************************/")
        print("")


class ConvertHelper:
    def __init__(self, id, index, title, url=None, date_added=time.time(), icon=None, icon_uri=None, tags=None):
        self.tags = tags
        self.icon_uri = icon_uri
        self.icon = icon
        self.url = url
        self.date_added = date_added
        self.title = title
        #  在当前文件夹index
        self.index = index
        self.id = id
        self.folder = {
            "type": "folder",
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "date_added": self.date_added,
            "children": [],
        }

        self.url_item = {
            "type": "url",
            "id": self.id,
            "index": self.index,
            "title": self.title,
            "date_added": self.date_added,
            "url": self.url,
            "icon": self.icon,
            "iconuri": self.icon_uri,
            "tags": self.tags,
        }

    @property
    def get_folder(self):
        return self.folder

    @property
    def get_url_item(self):
        return self.url_item


# 将聚簇结果标记写入数据
def save_cluster_result(bookmark_content, bookmarks_result, clustering_result, map_dict):
    for index, label in enumerate(clustering_result):
        bookmark_index = map_dict[index]
        bookmarks_result[bookmark_index][3] = label
        result = defaultdict(list)
        cluster_content = defaultdict(list)
        for item in bookmarks_result:
            key = str(item[3])
            result[key].extend([item[0], item[1]])
            if int(item[3]) >= 0 and len(item) >= 5:
                cluster_content[key].append(item[5].lower())
    marks_result = ConvertHelper(id=0, index=0, title='root').get_folder
    id_index = 1
    for key, value in result.items():

        title = calu_cluster_name(cluster_content, key)
        print(title)
        print(list(zip(value[0:len(value):2], value[1:len(value):2])))
        main_folder = ConvertHelper(id=id_index, index=1, title=title).get_folder
        id_index += 1
        for item_index, (url, title) in enumerate(zip(value[0:len(value):2], value[1:len(value):2])):
            main_folder['children'].append(
                ConvertHelper(id=id_index, index=item_index, title=title, url=url).get_url_item)
            id_index += 1
        marks_result['children'].append(main_folder)
    with open('data.json', 'w') as f:
        f.write(json.dumps(marks_result))
        print('dumps to dada.json')


def apart_dict(raw_content, key, value):
    """
    """
    result = list()
    if type(raw_content) == type({}):
        if value == raw_content.get(key):
            result.append(raw_content)
        else:
            for k in raw_content.keys():
                temp_result = apart_dict(raw_content[k], key, value)
                if temp_result:
                    result.extend(temp_result)
    if type(raw_content) == type([]):
        for item in raw_content:
            if type(item) == type({}):
                if value == item.get(key):
                    result.append(item)
                else:
                    for k in item.keys():
                        temp_result = apart_dict(item[k], key, value)
                        if temp_result:
                            result.extend(temp_result)
    return result


def get_bookmarks(args):
    bookmark_file = open(args.file, 'r')
    bookmark_content = bookmark_file.read()
    return bookmark_content


def string_md5(content):
    m = hashlib.new('ripemd160')
    m.update(content.encode('utf-8'))
    return m.hexdigest()


def convert_json2html():
    # initialize the class passing in the path to the bookmarks file to convert
    bookmarks = BookmarksConverter("data.json")

    # parse the file passing the format of the source file; "db", "html" or "json"
    bookmarks.parse("json")

    # convert the bookmarks to the desired format by passing the fomrat as a string; "db", "html", or "json"
    bookmarks.convert("html")

    # at this point the converted bookmarks are stored in the 'bookmarks' attribute.
    # which can be used directly or exported to a file.
    bookmarks.save()
    print("json to html successful")


def main(args):
    # 打开导出的书签文件
    bookmark_content = get_bookmarks(args)
    data_path = os.path.dirname(os.path.abspath(__file__)) + '/data'
    if not os.path.exists(data_path):
        os.mkdir(data_path)

    if args.file:
        bookmarks = get_bookmarks_from_export(bookmark_content)
    else:
        bookmarks = get_bookmarks_from_folder(bookmark_content)
    print("共计获得书签：%d 条" % len(bookmarks))

    # 下载或是从保存记录中加载所有的页面数据
    bookmarks_result = collect_page_content(bookmarks, data_path, args)
    print("抽取页面的内容")

    bookmarks_result = extract_text(bookmarks_result)
    # 提取文章的关键词，这一步可以省略
    # bookmarks_result = add_tags(bookmarks_result)
    if not args.kvalue:
        args.kvalue = int(len(bookmarks_result) / 20 + 1)

    # ks_result = extract_text(bookmarks_result)
    # 提取文章的关键词，这一步可以省略,其实没有任何用
    # bookmarks_result = add_tags(bookmarks_result)

    print("数据准备结束")

    map_dict, bookmark_corpus = cut_word(bookmarks_result)

    feature_matrix = extract_features(bookmark_corpus, args.debug)

    if args.method == "kmeans":
        clustering_result = kmeans_clustering(feature_matrix, args.kvalue, args.debug)
    else:
        clustering_result = hierarchical_clustering(feature_matrix, args.kvalue, args.debug)
    if args.debug:
        result, cluster_content = write_mark(bookmarks_result, clustering_result, map_dict)
        print_result(result, cluster_content)
        save_cluster_result(bookmark_content, bookmarks_result, clustering_result, map_dict)
    else:
        save_cluster_result(bookmark_content, bookmarks_result, clustering_result, map_dict)
    convert_json2html()


parser = argparse.ArgumentParser(description='chrome 书签自动分类工具')
parser.add_argument("-k", "--kvalue", type=int, help="聚簇的个数，将书签分为多少个簇")
parser.add_argument('-m', "--method", choices=['hierarchical', 'kmeans'], default="hierarchical",
                    help='选择聚类方法只有两种可选，kmeans和hierarchical')
parser.add_argument("-f", "--file", required=False,
                    help="书签文件的路径")
parser.add_argument("-d", "--debug", action='store_true', default=False, help="开启调试模式")
parser.add_argument("-p", "--proxy", help="页面抓取时使用代理")
parser.add_argument("-a", "--advance", action='store_true', default=False, help="开启此选项，加载历史文件时候发现页面没有抓取成功，会重新抓取")

args = parser.parse_args()
# print args
main(args)
