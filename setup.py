from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='plottr',
    version='0.1.0',
    description='A tool for live plotting and processing data',
    long_description=long_description,
    long_description_content_type="text/markdown",
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
            "plottr-inspectr = plottr.apps.inspectr:script",
            "plottr-autoplot-ddh5 = plottr.apps.autoplot:script",
        ],
    }
)
