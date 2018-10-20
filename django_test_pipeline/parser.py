import json
from objectify_json import ObjectifyJSON, Formatter
import requests
from .utils.io_yaml import read_yaml
from .colors import *


def parse_tests(path):
    data = read_yaml(path)
    return data


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
        self.post = self.session.post
        self.get = self.session.post

    @property
    def tests(self):
        return {x.id._data: x for x in self.config.tests}

    @property
    def login(self):
        login_info = self.config.login._data
        return login_info

    def start(self):
        for step in self.context.pipelines:
            print(cyan(step))
            for test_id in step:
                test = self.tests.get(test_id._data)
                if not test:
                    raise ParseException(
                        'test id {} does not exist'.format(test_id))
                print(
                    green('{} {}'.format(test.request.method._data.upper(),
                                         test.request.uri)))
