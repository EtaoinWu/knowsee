def must[T](x: T | None) -> T:
    return x  # type: ignore


def safe_must[T](
    x: T | None,
    entity_name: str | None = None,
    message: str | None = None,
) -> T:
    if x is None:
        if message is None:
            if entity_name is not None:
                message = f"Expected {entity_name} to be not None"
            else:
                message = "Expected value to be not None"
        raise ValueError(message)
    return x
