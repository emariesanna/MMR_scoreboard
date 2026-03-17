from collections import defaultdict
from typing import DefaultDict


def format_date(date_val) -> str:
    if hasattr(date_val, "strftime"):
        return date_val.strftime("%d-%b-%y")
    return str(date_val)

def round_dict_values(d: dict[str, float], decimals: int = 0) -> dict[str, int]:
    return {k: round(v, decimals) for k, v in d.items()}

def convert_bool(val) -> bool:
    return val=="TRUE"

def sum_dicts(dicts: list[dict[str, float]]) -> dict[str, float]:
    result = {}
    for d in dicts:
        for k, v in d.items():
            result[k] = result.get(k, 0) + v

    return result


def sum_default_dicts(dicts: list[dict[str, float] | DefaultDict[str, float]]) -> DefaultDict[str, float]:
    """Sum dictionaries preserving defaultdict default initialization when available."""
    default_factory = float
    first_default_dict_index = None

    for i, d in enumerate(dicts):
        if isinstance(d, defaultdict) and d.default_factory is not None:
            default_factory = d.default_factory
            first_default_dict_index = i
            break

    result: DefaultDict[str, float] = defaultdict(default_factory)

    # Seed from the first defaultdict without additive update to avoid doubling
    # the baseline value produced by the default factory.
    if first_default_dict_index is not None:
        for k, v in dicts[first_default_dict_index].items():
            result[k] = v

    for i, d in enumerate(dicts):
        if i == first_default_dict_index:
            continue
        for k, v in d.items():
            result[k] += v

    return result