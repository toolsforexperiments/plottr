from setuptools import setup, find_packages

setup(
    name='plottr',
    version='0.1.0',
    description='A tool for live plotting and processing data',
    author='Wolfgang Pfaff',
    author_email='wolfgangpfff@gmail.com',
    url='https://github.com/toolsforexperiments/plottr',
    packages=find_packages(),
    install_requires=[
        'pandas>=0.22',
        'xarray',
        'pyqtgraph>=0.10.0',
        'matplotlib',
        'numpy',
        'lmfit',
        'h5py>=2.10.0',
    ],
    entry_points={
        "console_scripts": [
            "plottr-monitr = plottr.apps.monitr:script",
        ],
    }
)
