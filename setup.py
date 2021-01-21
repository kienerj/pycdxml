import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="cdxml-styler",
    version="0.1.0",    
    author="Joos Kiener",
    author_email="joos.kiener@gmail.com",
    description="Change style of molecules in cdxml files",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kienerj/cdxml-styler",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta"
    ],
    python_requires='>=3.6'
)