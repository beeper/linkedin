import setuptools

from linkedin_matrix.get_version import git_tag, git_revision, version, linkified_version

try:
    long_desc = open("README.md").read()
except IOError:
    long_desc = "Failed to read README.md"

with open("requirements.txt") as reqs:
    install_requires = reqs.read().splitlines()

with open("optional-requirements.txt") as reqs:
    extras_require = {}
    current = []
    for line in reqs.read().splitlines():
        if line.startswith("#/"):
            extras_require[line[2:]] = current = []
        elif not line or line.startswith("#"):
            continue
        else:
            current.append(line)

extras_require["all"] = list({dep for deps in extras_require.values() for dep in deps})

with open("linkedin_matrix/version.py", "w") as version_file:
    version_file.write(f"""# Generated in setup.py

git_tag = {git_tag!r}
git_revision = {git_revision!r}
version = {version!r}
linkified_version = {linkified_version!r}
""")

setuptools.setup(
    name="linkedin-matrix",
    version=version,
    url="https://github.com/sumnerevans/linkedin-matrix",

    author="Sumner Evans",
    author_email="inquiries@sumnerevans.com",

    description="A Matrix-LinkedIn Messages puppeting bridge.",
    long_description=long_desc,
    long_description_content_type="text/markdown",

    packages=setuptools.find_packages(),

    install_requires=install_requires,
    extras_require=extras_require,
    python_requires="~=3.7",

    classifiers=[
        "Development Status :: 4 - Beta",
        "Topic :: Communications :: Chat",
    ],
    package_data={
        "linkedin_matrix": ["example-config.yaml"],
    },
    data_files=[
        (".", ["linkedin_matrix/example-config.yaml"]),
    ],
)

