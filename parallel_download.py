# -*- coding: utf-8 -*-

import queue
import threading
import time

import requests

headers = {
    'user-agent': 'Mozilla/5.0 (X11; Fedora; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
timeout = 5
max_retry_number = 3


class ParallelDownload(threading.Thread):
    def __init__(self, thread_id, in_queue, out_queue):
        threading.Thread.__init__(self)
        self.thread_id = thread_id
        self.in_queue = in_queue
        self.out_queue = out_queue

    def run(self):
        while self.in_queue.qsize() > 0:
            item = self.in_queue.get()
            serial_num = item[0]
            item_url = item[1][0]
            result = download_page_content(item_url)
            self.out_queue.put((serial_num, result))


count = 0
fail_url_count = 0


def download_page_content(url, proxies=None):
    """
    """
    global count, fail_url_count
    try_number = 1
    count += 1
    while try_number <= max_retry_number:
        try:
            if not proxies:
                response = requests.get(url, timeout=timeout, headers=headers)
            else:
                response = requests.get(url, proxies=proxies, timeout=timeout, headers=headers)
            status_code = response.status_code
            if status_code != 200:
                try_number += 1
            elif status_code == 200:
                # 判断页面的的编码，有些不标准的页面，request解码bug
                if response.encoding == "ISO-8859-1":
                    response.encoding = response.apparent_encoding
                return response.text
        except Exception as exception:
            print("Exception: {}".format(type(exception).__name__), "Exception message: {}".format(exception))
            print("The {0} fetch {1} failed. total_count {2}".format(try_number, url, count))
            try_number += 1
    if try_number > max_retry_number:
        fail_url_count += 1
        print('fail_url_count: ', fail_url_count)
    return None


# count = 1
#
#
# def download_page_content(url, proxies=None):
#     """
#     """
#     global count
#     try_numner = 1
#     status_code = 404
#     while try_numner <= max_retry_number:
#         try:
#             if not proxies:
#                 response = requests.get(url, timeout=timeout, headers=headers)
#             else:
#                 response = requests.get(url, proxies=proxies, timeout=timeout, headers=headers)
#             status_code = response.status_code
#         except:
#             print("The {0} fetch {1} failed.".format(try_numner, url.encode("utf-8")))
#         if status_code != 200:
#             try_numner += 1
#         else:
#             break
#     if status_code == 200:
#         # 判断页面的的编码，有些不标准的页面，request解码bug
#         if response.encoding == "ISO-8859-1":
#             response.encoding = response.apparent_encoding
#         print(count, url, response.status_code)
#         count += 1
#         return response.text
#     else:
#         return None


if __name__ == "__main__":
    in_queue = queue.Queue()

    out_queue = queue.Queue()

    in_queue.put((1, ["http://www.baidu.com", "baidu"]))
    in_queue.put((1, ["http://www.sina.com", "sina"]))
    in_queue.put((1, ["http://www.163.com", "163"]))
    for i in range(2):
        downloader = ParallelDownload("test" + str(i), in_queue, out_queue)
        downloader.daemon = True
        downloader.start()

    while threading.active_count() > 1:
        print(threading.active_count())
        time.sleep(1)

    while out_queue.qsize() > 0:
        item = out_queue.get()
        print(out_queue.qsize())
