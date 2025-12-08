import yaml


def main() -> None:
    """A simple function to satisfy mypy."""
    data: dict = yaml.safe_load("key: value")
    print(data)


if __name__ == "__main__":
    main()
