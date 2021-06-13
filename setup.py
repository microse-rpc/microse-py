import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="microse",
    version="1.1.2",
    author="A-yon Lee",
    author_email="i@hyurl.com",
    description="Micro Remote Object Serving Engine",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/microse-rpc/microse-py",
    keywords="rpc, micro-service, module-proxy",
    python_requires='>=3.6',
    packages=[
        "microse",
        "microse.rpc"
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
