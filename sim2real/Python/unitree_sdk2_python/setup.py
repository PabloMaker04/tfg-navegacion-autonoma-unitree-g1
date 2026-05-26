from setuptools import setup, find_packages

setup(
    name="unitree_sdk2py_g1",
    version="1.0.0",
    description="Python SDK para el robot Unitree G1 — espejo del SDK C++ unitree_sdk2",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=["unitree_sdk2py"],
)
