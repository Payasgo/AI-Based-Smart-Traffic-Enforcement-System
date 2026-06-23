from setuptools import setup, find_packages

setup(
    name="traffic_enforcement_ai",
    version="1.0.0",
    author="Kranthi Kumar Yarlagadda",
    author_email="payasgo55@gmail.com",
    description="Smarter Roads, Safer Lives — AI Traffic Enforcement System",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={
        "console_scripts": [
            "traffic-enforce=main:main",
        ]
    },
)
