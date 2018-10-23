import requests


def new_cookie(data):
    if not data:
        return
    jar = requests.cookies.RequestsCookieJar()
    for x in data:
        try:
            jar.set(x["name"], x["value"], domain=x["domain"], path=x.get("path", "/"))
        except KeyError as e:
            raise ParseException("missing {} in cookies".format(e))
    return jar


def to_tuple(value):
    if not value:
        return
    return tuple(value)
