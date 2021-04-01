import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="chemdraw-tools",
    version="0.1.0",    
    author="Joos Kiener",
    author_email="joos.kiener@gmail.com",
    description="Work with and convert between ChemDraw Formats",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/kienerj/chemdraw-tools",
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