"""Setup lambda_proxy."""

from setuptools import find_packages, setup

with open("README.md") as f:
    readme = f.read()


extra_reqs = {"test": ["pytest", "pytest-cov", "mock"]}


setup(
    name="aws-lambda-proxy",
    version="1.0.0",
    description="Simple AWS Lambda proxy to handle API Gateway request",
    long_description=readme,
    long_description_content_type="text/markdown",
    python_requires=">=3.10",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="AWS-Lambda API-Gateway Request Proxy",
    author="Lucas Messenger",
    author_email="1335960+layertwo@users.noreply.github.com",
    url="https://github.com/layertwo/aws-lambda-proxy",
    license="BSD",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    extras_require=extra_reqs,
)
