from plottr.utils import misc


def test_list_reorder():
    """Basic testing of list-reordering"""
    lst = ['a', 'b', 'f', 'z', 'x']
    neworder = ['b', 'f', 'x', 'z', 'a']
    order = misc.reorder_indices(lst, neworder)
    assert [lst[o] for o in order] == neworder

    order = misc.reorder_indices_from_new_positions(
        lst, b=0, f=1, x=2, z=3)
    assert [lst[o] for o in order] == neworder

