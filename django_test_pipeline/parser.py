import os
import json
import subprocess

from urllib.parse import urljoin, urlparse, urlencode

import requests
from objectify_json import ObjectifyJSON, Formatter
from printable import readable
from data_process.io_yaml import read_yaml
from .colors import *

DEBUG = os.getenv("DEBUG")


def parse_tests(path):
    data = read_yaml(path)
    return data


def get_terminal_size():
    rows, columns = subprocess.check_output(['stty', 'size']).split()
    return int(rows), int(columns)


TTY_ROWS, TTY_COLUMNS = get_terminal_size()


def print_row(char: str):
    print(char * TTY_COLUMNS)


class ParseException(Exception):
    pass


def print_json(data):
    if isinstance(data, ObjectifyJSON):
        data = data._data
    print(json.dumps(data, indent=2, ensure_ascii=False))


class TestPipeLine(Formatter):
    def __init__(self, path):
        """
        * parse orders:
            * read all as TestObject
            * parse next, add dependency
        * request
            * tests in same steps can be parallel
            * format variable references before request
            * do the request
            * then save response, validate assertion of headers and body
            * any fail will not go to next piped test
            * then next step
        """
        self.path = path
        config = parse_tests(path)
        self.config = ObjectifyJSON(config)
        self.context = ObjectifyJSON(config.copy())

        # requests
        self.session = requests.Session()
        self.get = self.session.get
        self.post = self.session.post

    @property
    def tests(self):
        return {x.id._data: x for x in self.config.tests}

    @property
    def login_info(self):
        login_info = self.config.login._data
        return login_info

    def start(self):
        for step in self.context.pipelines:
            print_row("=")
            print("{}: {}".format(cyan("STEP TESTS"), step))
            for test_id in step:
                test = self.tests.get(test_id._data)
                if not test:
                    raise ParseException(
                        'test id {} does not exist'.format(test_id))
                response = self.do_the_request(test)

    def parse_test(self, test):
        test = ObjectifyJSON(self.parse_dict(test._data))
        return test

    @property
    def base(self):
        base = self.context.base._data.lower()
        if not base.startswith('http'):
            base = 'http://' + base
        return base

    def do_the_request(self, test: ObjectifyJSON):
        # parse the test
        test = self.parse_test(test)

        print_row('-')
        test_id = test.id
        test = self.tests.get(test_id._data)
        url = urljoin(self.base, test.request.uri._data)
        # url_query = urlencode(test.request.query._data)
        print('{}: {} {}'.format(
            yellow(test.id), magenta(test.request.method._data.upper()),
            yellow(url)))
        if DEBUG:
            print("TEST DATA: ", repr(test))

        method = test.request.method._data.lower()
        request_func = getattr(self, method)
        """
        def request(self, method, url,
                params=None, data=None, headers=None, cookies=None, files=None,
                auth=None, timeout=None, allow_redirects=True, proxies=None,
                hooks=None, stream=None, verify=None, cert=None, json=None):
        """
        res = request_func(
            url,
            params=test.request.query._data,
            headers=test.request.headers._data,
            data=test.request.body._data,
        )

        self.validate_response(test, res)

    def validate_response(self, test: ObjectifyJSON, response):
        for rule_set in test.response:
            if DEBUG:
                print(cyan("RULE SET:"), rule_set)

            set_success = True
            for t in ['status', 'headers', 'body']:
                rule_part = getattr(rule_set, t)
                if t == 'status':
                    res_value_expression = ObjectifyJSON('status')
                    expect = rule_part
                    success = self.process_rule(res_value_expression, expect,
                                                t, response)
                    set_success = set_success and success

                elif rule_part:  # type: dict
                    for res_value_expression, expect in rule_part.items():
                        success = self.process_rule(res_value_expression,
                                                    expect, t, response)
                        set_success = set_success and success
            print("{}: {}".format(cyan("RULE SET RESULT"), set_success))

    def process_rule(self, res_value_expression: ObjectifyJSON,
                     expect: ObjectifyJSON, part_type: str, response):

        new_expression = self.parse_expression(res_value_expression._data,
                                               part_type)
        res_value = self.eval_rule_value(response, new_expression)
        # print result
        result = "{} == {}".format(res_value, expect)
        success = eval(result)
        color_fn = green if success else red
        print(new_expression, color_fn(result))
        return success

    def parse_expression(self, expression: str, part_type: str):
        if not startswithany(
                expression,
            ['self.', 'headers.', 'body.', 'res.', 'response.', 'status']):
            expression = '{}.'.format(part_type) + expression
        return expression

    def eval_rule_value(self, response, expression):
        status = ObjectifyJSON(response.status_code)
        headers = ObjectifyJSON(response.headers)
        body = ObjectifyJSON(response.json)
        res = response.json
        rv = eval(expression)
        if isinstance(rv, ObjectifyJSON):
            return rv._data
        return rv


def startswithany(s, prefix_list):
    for p in prefix_list:
        if s.startswith(p):
            return True
    return False
