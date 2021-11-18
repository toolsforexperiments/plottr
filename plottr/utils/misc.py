"""misc.py

Various utility functions.
"""

from enum import Enum
from typing import List, Tuple, TypeVar, Optional, Sequence, Any


def reorder_indices(lst: Sequence[str], target: Sequence[str]) -> Tuple[int, ...]:
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


class AutoEnum(Enum):
    """Enum that with automatically incremented integer values.

    Allows to pass additional arguments in the class variables to the __init__
    method of the instances.
    See: https://stackoverflow.com/questions/19330460/how-do-i-put-docstrings-on-enums/19330461#19330461
    """

    def __new__(cls, *args: Any) -> "AutoEnum":
        """creating a new instance.

        :param args: will be passed to __init__.
        """
        value = len(cls) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class LabeledOptions(AutoEnum):
    """Enum with a label for each element. We can find the name from the label
    using :meth:`.fromLabel`.

    Example::

            >>> class Color(LabeledOptions):
            ...     red = 'Red'
            ...     blue = 'Blue'

    Here, ``Color.blue`` has value ``2`` and ``Color.fromLabel('Blue')`` returns
    ``Color.blue``.
    """

    def __init__(self, label: str) -> None:
        self.label = label

    @classmethod
    def fromLabel(cls, label: str) -> Optional["LabeledOptions"]:
        """Find enum element from label."""
        for k in cls:
            if k.label.lower() == label.lower():
                return k
        return None
