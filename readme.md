# Requests Pipelines

It's a programmable tool to make you testing your APIs more handy.

## The execution order

* parse
    * read yaml as config
        * add `id` to every `test` in `tests`
    * parse next, add dependency (TODO)
* request
    * tests in the same step can be parallelize
    * format variable references before request
    * do the request
        * then save response to `test.results`, validate rules of header and body
        * any fail will raise an exception except you set `test.next.stop` to `false`
        * if `test.next.next_id` is set, the next test will be executed
    * then next step

## How to write the pipeline

The pipeline is defined in `yaml` file format. You can refer any data with `self.<name1>.<name2>`.

A **step** in defined as a array which contains `id`s of tests in the `self.pipelines`. The tests in a **step** will be execute concurrently (TODO).

After an HTTP request is done, the response result will be attached to the `test.results`, the `test` is the object in the `self.tests`, which will be accessed by it's `id`.

## Response structure in test

The response result returned by the `requests` library will be updated to the test in context, then you can refer to the value by `self.tests.<test_id>.results.<status_code>.<the value>`.

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
