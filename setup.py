from setuptools import setup, find_packages
setup(
    name = 'ankimd',
    version = '0.1.0',
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0",
        "python-frontmatter",
        "pyyaml",
        "requests",
    ],
    entry_points = {
        'console_scripts': [
            'ankimd = ankimd.__main__:main'
        ]
    })