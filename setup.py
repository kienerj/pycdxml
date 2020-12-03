import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="chemdraw-converter",
    version="0.0.1",    
    author="Joos Kiener",
    author_email="joos.kiener@gmail.com",
    description="Convert between ChemDraw Formats",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kienerj/chemdraw-converter",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta"
    ],
    python_requires='>=3.6',
    include_package_data=True
)