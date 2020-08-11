"""misc.py

Various utility functions.
"""

from typing import List, Tuple, TypeVar, Optional


def reorder_indices(lst: List, target: List) -> Tuple[int, ...]:
    """
    Determine how to bring a list with unique entries to a different order.

    Supports only lists of strings.

    :param lst: input list
    :param target: list in the desired order
    :return: the indices that will reorder the input to obtain the target.
    :raises: ``ValueError`` for invalid inputs.
    """
    if set([type(i) for i in lst]) != {str}:
        raise ValueError('Only lists of strings are supported')
    if len(set(lst)) < len(lst):
        raise ValueError('Input list elements are not unique.')
    if set(lst) != set(target) or len(lst) != len(target):
        raise ValueError('Contents of input and target do not match.')

    idxs = []
    for elt in target:
        idxs.append(lst.index(elt))

    return tuple(idxs)


def reorder_indices_from_new_positions(lst: List[str], **pos: int) \
        -> Tuple[int, ...]:
    """
    Determine how to bring a list with unique entries to a different order.

    :param lst: input list (of strings)
    :param pos: new positions in the format ``element = new_position``.
                non-specified elements will be adjusted automatically.
    :return: the indices that will reorder the input to obtain the target.
    :raises: ``ValueError`` for invalid inputs.
    """
    if set([type(i) for i in lst]) != {str}:
        raise ValueError('Only lists of strings are supported')
    if len(set(lst)) < len(lst):
        raise ValueError('Input list elements are not unique.')

    target = lst.copy()
    for item, newidx in pos.items():
        oldidx = target.index(item)
        del target[oldidx]
        target.insert(newidx, item)

    return reorder_indices(lst, target)


T = TypeVar('T')


def unwrap_optional(val: Optional[T]) -> T:
    """Covert a variable of type Optional[T] to T
    If the variable has value None a ValueError will be raised
    """
    if val is None:
        raise ValueError("Expected a not None value but got a None value.")
    return val
