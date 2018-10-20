# Requests Pipelines

## Response structure in test

The response result will be updated to the test in context, then you can refer to the value by `self.tests.<test_id>.results.<status_code>.<the value>`.

The `body` is the same as `json` field.

```
tests:
  a:
    results:
      "200":
        status: 200
        headers:
          a: 3
          b: 4
        text: ""
        json:
          a: 3
          b: 4
        body:
          a: 3
          b: 4
```
