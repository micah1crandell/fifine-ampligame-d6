from setuptools import setup, find_packages

setup(
    name="fifine-ampligame-d6",
    version="2.1.0",
    description="Pure standalone native USB driver and Bitfocus Companion bridge for Fifine AmpliGame D6.",
    author="Micah Crandell",
    packages=find_packages(),
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "fifine=fifine.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Topic :: System :: Hardware",
        "Topic :: System :: Hardware :: Hardware Drivers",
    ],
)
