from django_test_pipeline.parser import TestPipeLine


def main(args):
    p = TestPipeLine(args.file)
    p.start()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="yaml file wchich defines the test")
    args = parser.parse_args()

    main(args)
