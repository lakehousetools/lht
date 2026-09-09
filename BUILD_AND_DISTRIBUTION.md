# Building and Distributing LHT

This guide covers how to compile the LHT package with Cython and distribute it to PyPI.

## Prerequisites

1. **Python 3.9+** (matching your target distribution Python versions)
2. **Cython** installed: `pip install Cython`
3. **Build tools** installed: `pip install build twine`
4. **PyPI credentials** configured (see below)

## Setup

### 1. Activate Your Virtual Environment

```bash
source ./venv/bin/activate
# or
source venv_lht/bin/activate
```

### 2. Install Build Dependencies

```bash
pip install --upgrade setuptools Cython build twine
```

### 3. Configure PyPI Credentials

Create a `~/.pypirc` file with your PyPI credentials:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-your-production-token-here

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-token-here
```

**Note**: Use `__token__` as the username and your PyPI API token as the password. Get tokens from:
- Production: https://pypi.org/manage/account/token/
- Test: https://test.pypi.org/manage/account/token/

## Compiling with Cython

### Step 1: Clean Previous Builds (Optional)

```bash
# Remove old build artifacts
rm -rf dist/ build/ src/lht.egg-info/ *.egg-info/
```

### Step 2: Compile the Package

**For Development (Compiles in place):**
```bash
python setup.py build_ext --inplace
```

This creates `.so` files (or `.pyd` on Windows) alongside your source files in `src/lht/`.

**For Distribution (Builds wheel):**
```bash
python -m build
```

This creates:
- `dist/lht-X.X.X-py3-none-any.whl` (wheel file)
- `dist/lht-X.X.X.tar.gz` (source distribution)

### Step 3: Verify the Build

Check that compiled extensions were created:
```bash
find src/lht -name "*.so" -o -name "*.pyd"
```

You should see compiled files like:
- `src/lht/util/data_writer.cpython-313-darwin.so`
- `src/lht/salesforce/intelligent_sync.cpython-313-darwin.so`
- etc.

## Building for Distribution

### Build the Wheel

```bash
python -m build
```

The wheel will be created in the `dist/` directory with a name like:
- `lht-0.1.298-cp313-cp313-macosx_14_0_arm64.whl` (for your platform/Python version)

### Verify Wheel Contents (Optional)

To check what's included in the wheel:
```bash
# Unzip and inspect (wheels are just zip files)
unzip -l dist/lht-*.whl | grep -E "\.(so|py|pyd)$"
```

You should see:
- All `.so` files (compiled extensions)
- All `__init__.py` files
- No other `.py` source files (thanks to `BdistWheelWithoutSources` filtering)

## Installing a Local Build (No Upload)

You do not need PyPI or Test PyPI to test a build. Build, then install the wheel straight out of
`dist/`:

```bash
python -m build
pip install --force-reinstall dist/lht-2.0.79-cp314-cp314-macosx_26_0_arm64.whl
```

`--force-reinstall` is required. pip skips a version it believes is already installed, so
rebuilding the same version number and re-installing without it silently does nothing and you'll
be testing the old code.

Version numbers are irrelevant for local installs — rebuild and re-install the same version as
often as you like. Only reach for `publish.sh` when you actually intend to upload, since every run
of it consumes a version number.

Install into whichever venv runs the code you're testing, which is usually *not* this repo's venv.

### Installing on a Different Python or Platform

A wheel is built for exactly one interpreter and one platform — `cp314-macosx_26_0_arm64` means
CPython 3.14 on macOS arm64, and it will not install anywhere else. For any other target (a
different Python version, or Linux/EC2), install from the sdist, which compiles on arrival:

```bash
pip install dist/lht-2.0.79.tar.gz
```

That machine needs a C toolchain plus `Cython` and `setuptools`. On Debian/Ubuntu that's
`build-essential` and `python3-dev`.

## Publishing to PyPI

### Automated: `publish.sh`

`./publish.sh` from the repo root automates the rest of this section. It reads the current
version, proposes the next patch, verifies it against production PyPI, rewrites `pyproject.toml`,
cleans, builds, then prompts for test vs. prod and a token. Export `LHT_PYPI_TOKEN_TEST` or
`LHT_PYPI_TOKEN_PROD` to skip the token prompt.

Two things to know before running it:

- **It bumps the version on every run, including runs that fail afterwards.** A couple of failed
  attempts will skip several version numbers. Type an explicit version at the prompt to reuse one.
- **Its duplicate check queries production PyPI only.** Test PyPI keeps a separate version
  history, so an upload there can still fail with a `400` if that version already exists.

It leaves `pyproject.toml` modified on purpose — commit that yourself once the publish succeeds.

The remaining steps below are the manual equivalent.

### 1. Update Version Number

Before publishing, update the version in `pyproject.toml`:
```toml
[project]
version = "0.1.298"  # Increment this
```

### 2. Test on Test PyPI First

**Always test on Test PyPI before production!**

```bash
# Clean previous builds
rm -rf dist/ build/ src/lht.egg-info/

# Build the package
python -m build

# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*
```

You'll be prompted for your Test PyPI credentials (or use the token from `~/.pypirc`).

**Verify the upload:**
- Visit https://test.pypi.org/project/lht/
- Check that the version and files look correct

**Test installation:**
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ lht
```

**Note**: The `--extra-index-url` flag is required because Test PyPI doesn't have all dependencies (like `setuptools`, `Cython`). This tells pip to check regular PyPI for missing dependencies.

### 3. Publish to Production PyPI

Once you've verified everything works on Test PyPI:

```bash
# Clean previous builds
rm -rf dist/ build/ src/lht.egg-info/

# Build the package
python -m build

# Upload to Production PyPI
python -m twine upload --repository pypi dist/*
```

You'll be prompted for your PyPI credentials (or use the token from `~/.pypirc`).

**Verify the upload:**
- Visit https://pypi.org/project/lht/
- Check that the version appears correctly

## Building for Multiple Platforms

**Important**: Cython-compiled extensions are platform-specific. You need separate builds for:

- **Python versions**: 3.9, 3.10, 3.11, 3.12, 3.13, etc.
- **Platforms**: macOS, Linux, Windows
- **Architectures**: x86_64, arm64, etc.

### Recommended Approach: Use CI/CD

Set up GitHub Actions or similar CI/CD to automatically build for multiple platforms:

1. **GitHub Actions** - Build on push/release
2. **Build on each target platform** - macOS, Linux, Windows
3. **Build for each Python version** - Use `matrix` strategy
4. **Upload all wheels** - Use `twine upload` for each build

### Manual Multi-Platform Build

If building manually, you'll need to:

1. **Build on macOS** (for macOS wheels)
2. **Build on Linux** (for Linux wheels)
3. **Build on Windows** (for Windows wheels)

Or use Docker containers for different platforms.

## Troubleshooting

### Compilation Errors

**"Mixed use of tabs and spaces"**
- Convert all tabs to spaces in your Python files
- Use: `find src/lht -name "*.py" -exec sed -i '' 's/\t/    /g' {} \;`

**"local variable referenced before assignment"**
- Initialize variables before if/else blocks for Cython compatibility
- Example: `raw_value = None` before conditional blocks

**"wraparound" warnings**
- Already handled in `setup.py` with `wraparound: True`
- These are warnings, not errors

### Build and Environment Issues

**`No module named build`, even though you installed it**
- The wrong virtualenv is active. `publish.sh` and the commands in this guide invoke bare
  `python3`, so what matters is which interpreter is on `PATH` — not which directory you are in.
  The error line names the interpreter it actually used; if that path isn't this repo's venv,
  switch: `deactivate && source venv/bin/activate`.

**`publish.sh` passes its dependency check, then fails at `python3 -m build`**
- A leftover `build/` directory in the repo root. Python treats a directory without an
  `__init__.py` as a namespace package, so `import build` resolves to that directory and the
  script's guard passes spuriously. The script then deletes `build/` during its clean step, and
  the real `python3 -m build` fails. Remove `build/` first, or install `build` into the active
  venv.

**Source edits have no effect when importing from `src/`**
- Stale `.so` files are shadowing their `.py` sources; compiled extensions take import precedence
  over same-named Python files. `python setup.py build_ext --inplace` creates them, and they are
  **not** refreshed by `python -m build`, which compiles into `build/` instead. So an in-place
  build followed by later source edits leaves you importing old code. Clear them before testing
  sources:
  ```bash
  find src/lht -name "*.so" -delete
  ```
  They're gitignored build artifacts, so deleting them is always safe — rebuild to regenerate.
- To test what will actually ship, test the wheel rather than `src/`: unzip it somewhere and put
  that directory on `PYTHONPATH`, or `pip install --force-reinstall` it into a scratch venv.

### Distribution Issues

**"Package already exists"**
- Version number already exists on PyPI
- Increment version in `pyproject.toml`

**"Invalid credentials"**
- Check your `~/.pypirc` file
- Verify your PyPI token is correct
- Make sure you're using `__token__` as username

**"File already exists"**
- Delete old files in `dist/` directory
- Or use `--skip-existing` flag: `twine upload --skip-existing dist/*`

## Quick Reference

```bash
# Build and install locally — no upload, no version bump
python -m build
pip install --force-reinstall dist/lht-*.whl

# Automated publish (bumps version, builds, prompts test/prod)
./publish.sh

# Upload artifacts already sitting in dist/, without rebuilding
python -m twine upload --repository testpypi dist/*

# Full workflow for Test PyPI
rm -rf dist/ build/ src/lht.egg-info/
python -m build
python -m twine upload --repository testpypi dist/*

# Full workflow for Production PyPI
rm -rf dist/ build/ src/lht.egg-info/
python -m build
python -m twine upload --repository pypi dist/*

# Compile for development only (leaves .so files that shadow .py — see Troubleshooting)
python setup.py build_ext --inplace

# Clear stale in-place extensions so source edits take effect again
find src/lht -name "*.so" -delete
```

## Notes

- The `BdistWheelWithoutSources` class in `setup.py` filters the wheel after creation to exclude `.py` files (except `__init__.py`)
- Source `.py` files are needed during the build process for compilation, but are filtered out of the final wheel
- All `__init__.py` files are included (required for package structure)
- All compiled `.so` files are included in the wheel
- The `packages=find_packages(where='src')` and `package_dir={'': 'src'}` configuration ensures proper package structure
- Compiled extensions are platform and Python version specific

