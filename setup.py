from distutils.core import setup

setup(
    name='plottr',
    version='0.0.1',
    description='A tool for plotting data sent through a ZMQ socket',
    author='Wolfgang Pfaff',
    author_email='wolfgangpfff@gmail.com',
    url='https://github.com/wpfff',
    install_requires=[
        'pandas>=0.22',
        'xarray',
    ],
)
