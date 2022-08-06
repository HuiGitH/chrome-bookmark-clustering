## 说明

Fork from https://github.com/luchenqun/my-bookmark

一个聚簇的简单demo，对chrom导出书签进行简单分类。

在大佬已有的基础上进行改动:
1. `Python2`升级为`Python3`，使用` Python3.9.12`在macos上使用验证通过。
2. `Chrome`现在不支持导入`JSON`格式的书签，借助模块`bookmarks_converter`,将`JSON`格式的数据转换为`HTML`格式，支持导入。
3. 关键地方捕获一些异常

## 使用前准备
首先需要导出你的chrome书签。在chrome地址栏输入：
```plain
chrome://bookmarks/
```
在打开页面中点击`organize` ---->>> `Export bookmarks to HTML file`

如下图：
 ![](images/screenshot.jpg) 

保存文件后可以将文件路径作为命令的书签文件路径即可运行。

分类之前的书签：
![img.png](images/img.png)



## 安装依赖

在文件夹下输入命令：
```shell
pip install -r requirements.txt
```

## 安装使用

文件下输入下面命令，查看帮助文档：
```shell
python ./cluster.py -h
usage: cluster.py [-h] [-k KVALUE] -m {hierarchical,kmeans} -f FILE [-d] [-p PROXY]

chrome 书签自动分类工具

optional arguments:
  -h, --help            show this help message and exit
  -k KVALUE, --kvalue KVALUE
                        聚簇的个数,将书签分为多少个簇
  -m {hierarchical,kmeans}, --method {hierarchical,kmeans}
                        选择聚类方法只有两种可选,kmeans和hierarchical
  -f FILE, --file FILE  书签文件的路径
  -d, --debug           开启调试模式
  -p PROXY, --proxy PROXY
                        页面抓取时使用代理
```
例如使用文件包自带的例子使用如下命令：
```shell
python cluster.py -m hierarchical -f ./bookmarks_demo.html -k 15
```
上述命令的含义是使用层次聚簇，聚为15个簇，将`bookmarks_demo.html`中的书签分类为15个文件夹到`output_data_001.html`中

将`output_data_001.html`导入到浏览器

分类后的书签：
![img.png](images/img1.png)