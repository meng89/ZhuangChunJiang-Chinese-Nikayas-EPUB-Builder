#!/bin/env python3

import datetime
import threading
from urllib.parse import urlparse, urljoin

import epubuilder.epub3
import epubuilder.tools
import jinja2
import os
import re

import utils
from config import BOOKS_DIR

homepage = 'https://meng89.github.io/nikaya'


class Content:
    def __init__(self):
        self.url = None


def get_toc(url):

    father_title = None
    father_no = None

    toc = []

    soup = utils.url_to_soup(url)[0]

    for table in soup.find_all('table')[3:]:
        all_a = table.find_all('a')

        if len(all_a) == 1:
            # 1.諸天相應(請點選經號進入)：
            # 9集(請點選經號進入)：
            m = re.match('^(\d+)\.?(\S+)\(請點選經號進入\)：$', all_a[0].text)
            if m:
                father_no = m.group(1)
                father_title = m.group(2)
            else:
                raise Exception

        elif len(all_a) > 1:
            # 跳过目录中 相应 或 集 列表
            if [a['href'].startswith('#') for a in all_a].count(True) == len(all_a):
                continue

            for a in all_a:

                # 跳过底部 目录 链接
                m = re.match('\d+(-\d+)?', a.text)
                if not m:
                    continue

                content = {}

                if urlparse(a['href']).netloc:
                    sutra_url = a['href']
                else:
                    sutra_url = urljoin(url, a['href'])

                content['url'] = sutra_url

                content['sutra_no_start'] = a.text.split('-')[0]
                content['sutra_no_end'] = a.text.split('-')[-1]

                if father_no:
                    content['father_no'] = father_no
                if father_title:
                    content['father_title'] = father_title

                print(content)
                toc.append(content)

    exit()
    return toc


def get_xhtml_str(template, head_title, title, head_lines, main_lines, pali, js_path, css_path=None):

    sutra_xhtml_str = template.render(head_title=head_title,
                                      title=title,
                                      js_path=js_path,
                                      css_path=css_path or '',
                                      chinese_head='\n'.join(['<p>'+l+'</p>' for l in head_lines if l.strip()]),
                                      chinese_main='\n'.join(['<p>'+l+'</p>' for l in main_lines if l.strip()]),
                                      pali='\n'.join(['<p>'+l+'</p>' for l in pali.strip().splitlines() if l.strip()])
                                      )
    return sutra_xhtml_str


def make(make_tree, get_pages, book_info, built_books_dir):
    from epubuilder.public.metas import Language, Title
    from epubuilder.public import File
    from epubuilder.epub3 import Section

    sources = get_toc(book_info['url'])
    tree = make_tree(sources)

    book = epubuilder.epub3.Epub3()

    book.metadata.append(Language('zh-TW'))
    book.metadata.append(Title(book_info['title_chinese']))

    js_path = 'Scripts/a.js'
    book.files[js_path] = File(open('xhtml/js/a.js', 'rb').read())

    pages = get_pages(tree)
    sutra_template = jinja2.Template(open('xhtml/templates/sutra.xhtml', 'r').read())
    introduction_template = jinja2.Template(open('xhtml/templates/说明.xhtml', 'r').read())

    gmt_format = '%a, %d %b %Y %H:%M:%S GMT'
    modified_time = None

    # '%Y-%m-%d %H:%M:%S'

    for page in pages:

        js_relative_path = epubuilder.tools.relative_path(js_path, os.path.split(page['epub_expected_path'])[0])

        sutra_xhtml_str = get_xhtml_str(sutra_template, page['head_title'], page['title'], page['head_lines'],
                                        page['main_lines'],
                                        page['pali'], js_relative_path)

        page_path = book.add_page(sutra_xhtml_str.encode(), page['epub_expected_path'])
        book.set_toc(page['epub_toc'], page_path)

        print(book_info['title_chinese'], page['epub_toc'], page_path)

        cur_page_modified = datetime.datetime.strptime(page['last_modified'], gmt_format)

        if modified_time:
            modified_time = cur_page_modified if cur_page_modified > modified_time else modified_time
        else:
            modified_time = cur_page_modified

    created_time = datetime.datetime.now()

    introduction = introduction_template.render(homepage=homepage,
                                                modified_time=modified_time.strftime('%Y-%m-%d'),
                                                created_time=created_time.strftime('%Y-%m-%d %H:%M'))
    introduction_path = 'introduction.xhtml'
    book.files[introduction_path] = File(introduction.encode())

    book.toc.insert(0, Section('说明', href=introduction_path))

    filename = book_info['title_chinese'] + '.epub'

    book.write('{}/{}'.format(built_books_dir, filename))
    return filename, modified_time, created_time


class RunCccThread(threading.Thread):
    def __init__(self, host, port):
        super().__init__()
        self._host = host
        self._port = port

    def run(self):
        from run_ccc import app
        app.run(host=self._host, port=self._port, debug=False)


def is_socket_open(host, port):
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind((host, port))
        s.close()
        return True
    except OSError:
        return False


def main():
    os.makedirs(BOOKS_DIR, exist_ok=True)

    _host = '127.0.0.1'
    _port = 1080

    while True:
        if is_socket_open(_host, _port):
            break
        else:
            _port += 1

    run_ccc_thread = RunCccThread(_host, _port)
    run_ccc_thread.daemon = True
    run_ccc_thread.start()

    import time
    time.sleep(3)

    url_part = 'http://{}:{}'.format(_host, _port)

    import sn
    import mn
    import dn
    import an

    sn_info = {'title_chinese': '相應部', 'title_pali': 'Saṃyutta Nikāya', 'url': url_part + '/SN/index.htm'}
    mn_info = {'title_chinese': '中部', 'title_pali': 'Majjhima Nikāya', 'url': url_part + '/MN/index.htm'}
    dn_info = {'title_chinese': '長部', 'title_pali': 'Digha Nikāya', 'url': url_part + '/DN/index.htm'}
    an_info = {'title_chinese': '增支部', 'title_pali': 'Aṅguttara nikāya', 'url': url_part + '/AN/index.htm'}

    # items = []
    for module, info in ((sn, sn_info), (mn, mn_info), (dn, dn_info), (an, an_info))[:]:
        make(module.make_tree, module.get_pages, info, BOOKS_DIR)

    exit()

if __name__ == '__main__':
    main()
