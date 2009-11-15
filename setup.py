from setuptools import setup, find_packages

setup(
    name="SpaghettiFS",
    version="0.1",
    description="Git-backed FUSE filesystem",
    keywords="git filesystem",
    url="http://github.com/alex-morega/SpaghettiFS",
    license="BSD License",
    author="Alex Morega",
    author_email="public@grep.ro",
    packages=find_packages(),
    setup_requires=['nose>=0.11'],
    install_requires=['dulwich>=0.3.3', 'fusepy>=1.0.r33'],
    test_suite="nose.collector",
    entry_points={
        'console_scripts': [
            'spaghettifs = spaghettifs.cmd:main',
        ],
    },
)
