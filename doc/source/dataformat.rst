.. documentation of the internal data formats.

Data formats
============

A DataDict container can contain multiple `data fields` (or variables), that have values and can contain their own meta information. Importantly, we distinct between independent fields (the `axes`) and dependent fields (the `data`).

Despite the naming, `axes` is not meant to imply that the `data` have to have a certain shape (but the degree to which this is true depends on the class used). A list of classes for different shapes of data can be found below.

The basic structure of data conceptually looks like this (we inherit from `dict`) ::

        {
            'data_1' : {
                'axes' : ['ax1', 'ax2'],
                'unit' : 'some unit',
                'values' : [ ... ],
                '__meta__' : 'This is very important data',
                ...
            },
            'ax1' : {
                'axes' : [],
                'unit' : 'some other unit',
                'values' : [ ... ],
                ...,
            },
            'ax2' : {
                'axes' : [],
                'unit' : 'a third unit',
                'values' : [ ... ],
                ...,
            },
            '__globalmeta__' : 'some information about this data set',
            '__moremeta__' : 1234,
            ...
        }

In this case we have one dependent variable, ``data_1``, that depends on two axes, ``ax1`` and ``ax2``. This concept is restricted only in the following way:

* a dependent can depend on any number of independents
* an independent cannot depend on other fields itself
* any field that does not depend on another, is treated as an axis

Note that meta information is contained in entries whose keys start and end with double underscores. Both the DataDict itself, as well as each field can contain meta information.

In the most basic implementation, the only restriction on the data values is that they need to be contained in a sequence (typically as list, or numpy array), and that the length of all values in the data set (the number of `records`) must be equal. Note that this does not preclude nested sequences!


Relevant data classes
---------------------
:DataDictBase: The main base class. Only checks for correct dependencies. Any requirements on data structure is left to the inheriting classes.
:DataDict: The only requirement for valid data is that the number of records is the same for all data fields.


API documentation for the datadict module
-----------------------------------------

.. automodule:: plottr.data.datadict
    :members:
