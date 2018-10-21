import os
import json
import sys
import subprocess
from urllib.parse import urljoin, urlparse, urlencode
from concurrent.futures import ThreadPoolExecutor

import requests
from objectify_json import ObjectifyJSON, Formatter
from printable import readable
from data_process.io_yaml import read_yaml
from .colors import *
from .thread_local import ThreadLocalData

DEBUG = os.getenv("DEBUG")

THREAD = ThreadLocalData()


class ParseException(Exception):
    pass


def get_terminal_size():
    rows, columns = subprocess.check_output(["stty", "size"]).split()
    return int(rows), int(columns)


TTY_ROWS, TTY_COLUMNS = get_terminal_size()


def parse_tests(path):
    data = read_yaml(path)
    for id, t in data["tests"].items():
        t["id"] = id
    return data


def print_thread(*args, **kwargs):
    THREAD.print(*args, **kwargs)


def print_row(char: str):
    print_thread(char * TTY_COLUMNS)


def println_any(data, name=None):
    if isinstance(data, ObjectifyJSON):
        data = data._data
    if not data:
        return

    if name:
        print_thread(cyan(name))

    def _default(o):
        rv = repr(o)
        if isinstance(rv, str):
            try:
                return json.loads(rv)
            except:
                pass
            try:
                return eval(rv)
            except:
                pass
        return rv

    if isinstance(data, (list, tuple, dict)):
        print_thread(json.dumps(data, indent=2, ensure_ascii=False, default=_default))
    else:
        print_thread(data)


def print_inline(name, data, color=cyan):
    if isinstance(data, ObjectifyJSON):
        data = data._data
    if isinstance(data, str) and not data:
        return
    print_thread("{}: {}".format(color(name), data))


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
        self.context = ObjectifyJSON(config)

        # requests
        self.session = requests.Session()
        self.get = self.session.get
        self.post = self.session.post

        # worker pool
        self.pool = ThreadPoolExecutor()

    @property
    def tests(self) -> ObjectifyJSON:
        return self.context.tests

    def get_test(self, id) -> ObjectifyJSON:
        if isinstance(id, ObjectifyJSON):
            id = id._data
        if not id:
            return ObjectifyJSON(None)
        return getattr(self.tests, id)

    @property
    def login_info(self):
        login_info = self.context.login._data
        return login_info

    def start(self):
        for index, step in enumerate(self.context.pipelines, start=1):
            print_row("=")
            print_inline("TESTS {}".format(index), step)

            def fn(test_id):
                test = self.get_test(test_id)
                if not test:
                    raise ParseException("test id {} does not exist".format(test_id))
                response = self.do_the_request(test, test_id)
                return response, THREAD.get_stdout_value()

            future = self.pool.map(fn, step)
            for response, stdout in future:
                print(stdout)

    def parse_test(self, test: ObjectifyJSON):
        results = test._data.pop("results", None)
        parsed = self.parse_dict(test._data)
        if results:
            parsed["results"] = results
        test = ObjectifyJSON(parsed)
        return test

    @property
    def base(self):
        base = self.context.base._data.lower()
        if not base.startswith("http"):
            base = "http://" + base
        return base

    def do_the_request(self, test: ObjectifyJSON, continue_next=True):
        # parse the test
        test = self.parse_test(test)
        print_row("-")
        if DEBUG:
            print_inline("Test Data: ", repr(test))
            println_any(self.tests, name="Tests Data")

        test_id = test.id
        test = self.get_test(test_id)
        req = test.request
        url = urljoin(self.base, req.uri._data)
        method = req.method._data or "get"

        self.debug_request(test.id._data, req, method, url)

        request_func = getattr(self, method, getattr(self.session, method.lower()))
        """
        def request(self, method, url,
                params=None, data=None, headers=None, cookies=None, files=None,
                auth=None, timeout=None, allow_redirects=True, proxies=None,
                hooks=None, stream=None, verify=None, cert=None, json=None):
        """
        mapping = [
            ("params", "query"),
            ("headers", "headers"),
            ("data", "body"),
            ("cookies", "cookies"),
            ("files", "files"),
            ("proxies", "proxies"),
            ("timeout", "timeout"),
        ]
        kwargs = {x[0]: getattr(test.request, x[1])._data for x in mapping}
        if not kwargs.get("timeout"):
            kwargs["timeout"] = 10
        try:
            response = request_func(url, **kwargs)
        except Exception as e:
            print_inline(test_id, str(e))
            return

        self.validate_response(test, response, continue_next)
        return response

    def validate_response(self, test: ObjectifyJSON, response, continue_next=True):
        if not test.response:
            print_thread(red("Warning: test has not defined the response rules"))
            return

        rule_dict = {s.status._data: s for s in test.response}
        assert None not in rule_dict, "must give the status"

        # validate the status
        res_value_expression = ObjectifyJSON("status")
        expect = "None"
        result_dict = self.process_rule(
            res_value_expression, expect, "response.status", response
        )
        status = result_dict["Value"]

        # attach response
        self.attach_request_response(test, response)

        # get the rule set
        rule = rule_dict.get(status)
        if not rule:
            print_thread(
                red("Warning: response status {} is not handled".format(status))
            )
            return

        # debug the response
        self.debug_response(rule, response)

        # validate the rule set
        results = []
        for t in ["headers", "body"]:
            rule_part = getattr(rule, t)
            if rule_part:  # type: dict
                for res_value_expression, expect in rule_part.items():
                    result_dict = self.process_rule(
                        res_value_expression, expect, t, response
                    )
                    results.append(result_dict)

        print_inline("Rule", rule)
        if results:
            println_any(magenta(readable(results)), name="Rule Detail")
            success = all(x["Success"] for x in results)
        else:
            success = True
        color_fn = green if success else red
        print_inline("Rule Result", color_fn(success))

        stop = rule.stop._data
        if stop is None:
            stop = True

        if not success and stop:
            print_thread("Test pipeline is stopped at test {}!".format(test.id._data))
            sys.exit(1)

        # try next test
        if continue_next:
            self.try_next_test(test, rule, response, success)

    def debug_request(
        self, test_id: str, request: ObjectifyJSON, method: str, url: str
    ):
        url_query = urlencode(request.query._data or {})
        print_thread(
            "{}: {} {} | {}".format(
                yellow(test_id), magenta(method.upper()), yellow(url), blue(url_query)
            )
        )
        println_any(request.headers._data, name="Request Headers")

    def debug_response(self, rule: ObjectifyJSON, response):
        debug = rule.debug._data
        if not debug:
            return
        if "headers" in debug:
            _headers = response.headers._store
            println_any(
                {v[0]: v[1] for v in _headers.values()}, name="Response Headers"
            )
        if "body" in debug:
            body_json = self._get_json_from_response(response)
            if body_json:
                println_any(body_json, name="Response Body")
            else:
                println_any(response.text, name="Response Text")

    def try_next_test(
        self, pre_test: ObjectifyJSON, rule: ObjectifyJSON, response, success: bool
    ):
        next = rule.next
        next_id = next.id._data
        if not next_id:
            return

        next_test = self.get_test(next_id)
        if next and next_id:
            if not next_test:
                raise ParseException("next id {} does not exist".format(next_id))

            if_success = next.if_success._data
            # default is True
            if if_success is None:
                if_success = True

            if DEBUG:
                print_inline("If Success", if_success)

            if if_success and not success:
                return

            # do the next request
            continue_next = next.continue_next._data
            if continue_next is None:
                continue_next = True
            self.do_the_request(next_test, continue_next)

    def process_rule(
        self,
        res_value_expression: ObjectifyJSON,
        expect: ObjectifyJSON,
        part_type: str,
        response,
    ):
        if isinstance(expect, ObjectifyJSON):
            expect = expect._data
        new_expression = self.parse_expression(res_value_expression._data, part_type)
        res_value = self.eval_rule_value(response, new_expression)
        # print result
        result = "{} == {}".format(res_value, expect)
        success = res_value == expect
        result_dict = {
            "Expression": new_expression,
            "Value": res_value,
            "Expect": expect,
            # "Types": "{}, {}".format(type(res_value), type(expect)),
            "Success": success,
        }
        return result_dict

    def parse_expression(self, expression: str, part_type: str):
        if not startswithany(
            expression,
            ["self.", "headers.", "json.", "response.", "status", "text.", "tests."],
        ):
            if expression.startswith("["):
                expression = "{}{}".format(part_type, expression)
            else:
                expression = "{}.{}".format(part_type, expression)
        return expression

    def attach_request_response(self, test: ObjectifyJSON, response):
        results = test._data.setdefault("results", {})
        request_context = {
            "response": response,
            "status": response.status_code,
            "headers": response.headers,
            "text": response.text,
            "json": self._get_json_from_response(response),
            "body": self._get_json_from_response(response),
            "content": response.content,
            "cookies": response.cookies,
            "history": response.history,
        }
        results[str(response.status_code)] = request_context
        return request_context

    def _get_json_from_response(self, response):
        try:
            js = response.json()
        except json.decoder.JSONDecodeError:
            js = {}
        return js

    def eval_rule_value(self, response, expression):
        status = ObjectifyJSON(response.status_code)
        headers = {v[0]: v[1] for v in response.headers._store.values()}
        text = ObjectifyJSON(response.text)
        json = ObjectifyJSON(self._get_json_from_response(response))
        body = json

        tests = self.tests

        try:
            rv = eval(expression)
        except Exception as e:
            print_thread(expression)
            raise
        if isinstance(rv, ObjectifyJSON):
            return rv._data
        return rv


def startswithany(s, prefix_list):
    for p in prefix_list:
        if s.startswith(p):
            return True
    return False
