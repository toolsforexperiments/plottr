from setuptools import setup, find_packages

import versioneer

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='plottr',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description='A tool for live plotting and processing data',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Wolfgang Pfaff',
    author_email='wolfgangpfff@gmail.com',
    url='https://github.com/toolsforexperiments/plottr',
    packages=find_packages(include=("plottr*",)),
    package_data={'plottr': ['resource/gfx/*']},
    install_requires=[
        'pandas>=0.22',
        'xarray',
        'pyqtgraph>=0.10.0',
        'matplotlib',
        'numpy',
        'lmfit',
        'h5py>=2.10.0',
        'qtpy>=1.9.0'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Topic :: Scientific/Engineering'
    ],
    python_requires='>=3.6',
    extras_require={'PyQt5': "PyQt5", "PySide2": "PySide2"},
    entry_points={
        "console_scripts": [
            "plottr-monitr = plottr.apps.monitr:script",
            "plottr-inspectr = plottr.apps.inspectr:script",
            "plottr-autoplot-ddh5 = plottr.apps.autoplot:script",
        ],
    }
)
