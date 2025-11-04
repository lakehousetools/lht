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

## Publishing to PyPI

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
# Full workflow for Test PyPI
rm -rf dist/ build/ src/lht.egg-info/
python -m build
python -m twine upload --repository testpypi dist/*

# Full workflow for Production PyPI
rm -rf dist/ build/ src/lht.egg-info/
python -m build
python -m twine upload --repository pypi dist/*

# Compile for development only
python setup.py build_ext --inplace
```

## Notes

- The `BdistWheelWithoutSources` class in `setup.py` filters the wheel after creation to exclude `.py` files (except `__init__.py`)
- Source `.py` files are needed during the build process for compilation, but are filtered out of the final wheel
- All `__init__.py` files are included (required for package structure)
- All compiled `.so` files are included in the wheel
- The `packages=find_packages(where='src')` and `package_dir={'': 'src'}` configuration ensures proper package structure
- Compiled extensions are platform and Python version specific

