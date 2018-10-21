# Requests Pipelines

It's a programmable tool to make you testing your APIs more handy.

## How to write the pipeline

The pipeline is defined in `yaml` file format. You can refer any data of it via `self.<name1>.<name2>`.

A pipeline have many **test**, which is the object in the `self.tests` and have an `id` key with a detail object as it's value.

A **step** in defined as a array which contains `id`s of tests in the `self.pipelines`. The tests in a **step** will be execute concurrently (TODO).

After an HTTP request is done, it's response will be compared to the **rule** identified by it's `status` code. One test (request) can have multiple **rules**.

And the response result will be attached to the `test.results`,  which can be accessed by the test's `id` and response's status.

## The execution order

* Parse
    * Read yaml as config
        * Add `id` to every `test` in `tests`
    * Parse next, add dependency (TODO)
* Request
    * Tests in the same step can be parallelize
    * Format variable references before request
    * Do the request
        * Then save response to `test.results`, validate rules of header and body.
        * Any fail will raise an exception except you set `rule.next.stop` to `false`.
        * If `rule.next.next_id` is set, the next test will be executed.
        * If the next test defined by `next_id` has it's next test, the program will follow up to execute it, unless you set `rule.next.continue_next` to `false`.
    * Then next step

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
        content: ""
        cookies:
          a: 3
          b: 4
        history:
          - response1
          - response2
```
