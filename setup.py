from setuptools import setup, find_packages

setup(
    name='plottr',
    version='0.0.1',
    description='A tool for plotting data sent through a ZMQ socket',
    author='Wolfgang Pfaff',
    author_email='wolfgangpfff@gmail.com',
    url='https://github.com/wpfff',
    packages=find_packages(),
    install_requires=[
        'pandas>=0.22',
        'xarray',
    ],
    entry_points={'console_scripts': ['plottr=plottr.plottr:console_entry',
                                      'inspectr=plottr.qcodes_dataset_inspectr'
                                      ':console_entry']}
)
