from setuptools import setup, find_packages

setup(
    name='plottr',
    version='0.1.0',
    description='A tool for live plotting and processing data',
    author='Wolfgang Pfaff',
    author_email='wolfgangpfff@gmail.com',
    url='https://github.com/wpfff/plottr',
    packages=find_packages(),
    install_requires=[
        'pandas>=0.22',
        'xarray',
        'pyqtgraph>=0.10.0',
        'matplotlib',
        'numpy',
    ],
)
