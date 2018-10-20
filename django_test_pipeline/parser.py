import os
import json
import sys
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

    def do_the_request(self, test: ObjectifyJSON, continue_next=True):
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

        self.validate_response(test, res, continue_next)

    def validate_response(self,
                          test: ObjectifyJSON,
                          response,
                          continue_next=True):
        rule_set_dict = {s.status._data: s for s in test.response}
        assert None not in rule_set_dict, 'must give the status'

        # validate the status
        res_value_expression = ObjectifyJSON('status')
        expect = 'None'
        result_dict = self.process_rule(res_value_expression, expect,
                                        'response.status', response)
        status = result_dict['Value']

        # get the rule set
        rule_set = rule_set_dict.get(status)
        if not rule_set:
            print(
                red('Warning: response status {} is not handled'.format(
                    status)))
            return

        # validate the rule set
        if DEBUG:
            print(cyan("RULE SET:"), rule_set)

        results = []
        for t in ['headers', 'body']:
            rule_part = getattr(rule_set, t)
            if rule_part:  # type: dict
                for res_value_expression, expect in rule_part.items():
                    result_dict = self.process_rule(res_value_expression,
                                                    expect, t, response)
                    results.append(result_dict)

        print(readable(results))
        success = all(x['Success'] for x in results)
        color_fn = green if success else red
        print("{}: {}".format(cyan("RULE SET RESULT"), color_fn(success)))

        stop = rule_set.stop._data
        if stop is None:
            stop = True

        if stop:
            print('Test pipeline is stopped at test {}!'.format(test.id._data))
            sys.exit(1)

        # try next test
        if continue_next:
            self.try_next_test(test, rule_set, response, success)

    def try_next_test(self, pre_test: ObjectifyJSON, rule_set: ObjectifyJSON,
                      response, success: bool):
        next = rule_set.next
        next_id = next.next_id._data
        next_test = self.tests.get(next_id)
        if next and next_id:
            if not next_test:
                raise ParseException(
                    'next id {} does not exist'.format(next_id))

            if_success = next.if_success._data
            # default is True
            if if_success is None:
                if_success = True

            if DEBUG:
                print("{}: {}".format(cyan("IF SUCCESS"), if_success))

            if if_success and not success:
                return

            # do the next request
            continue_next = next.continue_next._data
            if continue_next is None:
                continue_next = True
            self.do_the_request(next_test, continue_next)

    def process_rule(self, res_value_expression: ObjectifyJSON,
                     expect: ObjectifyJSON, part_type: str, response):

        new_expression = self.parse_expression(res_value_expression._data,
                                               part_type)
        res_value = self.eval_rule_value(response, new_expression)
        # print result
        result = "{} == {}".format(res_value, expect)
        success = eval(result)
        result_dict = {
            'Expression': new_expression,
            'Value': res_value,
            'Expect': expect,
            "Success": success,
        }
        return result_dict

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
