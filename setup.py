import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="alar",
    version="0.7.0",
    author="A-yon Lee",
    author_email="i@hyurl.com",
    description="The python version of alar engine.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hyurl/alar-py",
    python_requires='>=3.6',
    packages=[
        "alar"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        "websockets>=8.0"
    ]
)
