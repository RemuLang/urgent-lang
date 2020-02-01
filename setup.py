from setuptools import setup, find_packages
from pathlib import Path

with Path('README.md').open() as readme:
    readme = readme.read()

with Path('urgent/version.py').open() as version:
    exec(version.read())

setup(
    name='urgent',
    version=__version__ if isinstance(__version__, str) else str(__version__),
    keywords="", # keywords of your project that separated by comma ","
    description="", # a conceise introduction of your project
    long_description=readme,
    long_description_content_type="text/markdown",
    license='mit',
    python_requires='>=3.6.0',
    url='https://github.com/RemuLang/urgent',
    author='thautawarm',
    author_email='twshere@outlook.com',
    packages=find_packages(),
    entry_points={"console_scripts": ['ugt=urgent.cli:main']},
    install_requires=["rbnf-rts", "toml", 'argser', 'sijuiacion-lang', 'remu-operator'],
    platforms="any",
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    zip_safe=False,
)

