from setuptools import setup, find_packages

setup(
    name = "SpaghettiFS",
    version = "0.1",
    packages = find_packages(),
    install_requires = ['dulwich>=0.3.3'],
    author = "Alex Morega",
    author_email = "spaghettifs@grep.ro",
    description = "Git-backed FUSE filesystem",
    license = "BSD License",
    keywords = "hello world example examples",
    url = "http://github.com/alex-morega/spaghettifs",
    test_suite = "spaghettifs.tests.all",
    entry_points = {
        'console_scripts': [
            'spaghettifs = spaghettifs.cmd:main',
        ],
    },
)
