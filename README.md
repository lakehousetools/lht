# Steps to Push New Version to Test PyPI

## Prerequisites
1. **Install required tools:**
   ```bash
   pip install --upgrade pip setuptools wheel twine
   ```

2. **Create Test PyPI account** at https://test.pypi.org/account/register/ if you don't have one

3. **Generate API token** (recommended over password):
   - Go to https://test.pypi.org/manage/account/
   - Scroll to "API tokens" section
   - Click "Add API token"
   - Give it a name and set scope (project-specific or account-wide)
   - Copy the token (starts with `pypi-`)

## Step-by-Step Process

### 1. Update Version Number
Update the version in your package configuration:
- **setup.py**: Update the `version` parameter
- **setup.cfg**: Update version in `[metadata]` section
- **pyproject.toml**: Update version in `[project]` or `[tool.setuptools]`
- **__init__.py**: Update `__version__` variable if present

### 2. Clean Previous Builds
```bash
rm -rf build/ dist/ *.egg-info/
```

### 3. Build the Package
```bash
python -m build
```
Or if using older setuptools:
```bash
python setup.py sdist bdist_wheel
```

### 4. Check the Build
Verify the package was built correctly:
```bash
twine check dist/*
```

### 5. Upload to Test PyPI
Using API token (recommended):
```bash
twine upload --repository testpypi dist/*
```

When prompted:
- Username: `__token__`
- Password: [paste your API token]

Or specify credentials directly:
```bash
twine upload --repository testpypi dist/* --username __token__ --password pypi-your-token-here
```

### 6. Test Installation
Test that your package can be installed from Test PyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ your-package-name
```

If your package has dependencies from regular PyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ your-package-name
```

## Configuration File Method (Optional)

Create `~/.pypirc` file to store repository configurations:
```ini
[distutils]
index-servers =
    testpypi
    pypi

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-your-test-token-here

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi-your-production-token-here
```

Then upload with:
```bash
twine upload --repository testpypi dist/*
```

## Troubleshooting Tips

- **Version conflicts**: Each upload must have a unique version number
- **File already exists**: You cannot overwrite files; increment version number
- **Authentication errors**: Double-check your API token and username format
- **Network issues**: Try again or check your internet connection
- **Package validation**: Run `twine check dist/*` before uploading

## Next Steps
Once testing is complete on Test PyPI:
1. Upload to production PyPI using `twine upload dist/*` (without repository flag)
2. Test installation from production PyPI: `pip install your-package-name`

# Salesforce Integration Configuration

This project integrates with Salesforce to synchronize data between Salesforce and Snowflake.

## Prerequisites
- Admin has already created a Connected App in Salesforce
- Python environment with required dependencies (see `requirements.txt`)
- Access to the Salesforce org where the Connected App was created

## Configuration Steps

### Step 1: Gather Connected App Credentials
From the Salesforce admin, obtain the following information from the Connected App:
- **Consumer Key** (Client ID)
- **Consumer Secret** (Client Secret)
- **My Domain** (if using a custom domain)
- **Authorization Endpoint URL**
- **Token Endpoint URL**

### Step 2: Create Configuration File
Create a `.solomo/connections.toml` file in your project root with the following structure:

```toml
[salesforce_prod]
CLIENT_ID = 'your_consumer_key_here'
CLIENT_SECRET = 'your_consumer_secret_here'
AUTHORIZATION_BASE_URL = 'https://login.salesforce.com/services/oauth2/authorize'
TOKEN_URL = 'https://login.salesforce.com/services/oauth2/token'
REDIRECT_URI = 'https://localhost:1717/OauthRedirect'
SCOPE = "refresh_token full"
sandbox = false

# For sandbox environments, use:
# AUTHORIZATION_BASE_URL = 'https://test.salesforce.com/services/oauth2/authorize'
# TOKEN_URL = 'https://test.salesforce.com/services/oauth2/token'
# sandbox = true

# If using My Domain, add:
# MY_DOMAIN = "your_my_domain_name"
```

### Step 3: Install Required Dependencies
Install the Python packages listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Key dependencies for Salesforce integration:
- `requests` - For HTTP API calls
- `toml` - For configuration file parsing
- `lht` - Custom Salesforce integration library

### Step 4: Configure Authentication Method
The codebase supports two authentication methods:

#### Option A: Client Credentials Flow (Recommended for Server-to-Server)
Use the `login_user_flow()` function in `user/salesforce_auth.py`:

```python
from user import salesforce_auth as sf
import toml

config = toml.load("./.solomo/connections.toml")
config = config['salesforce_prod']

CLIENT_ID = config["CLIENT_ID"]
CLIENT_SECRET = config["CLIENT_SECRET"]
MY_DOMAIN = config.get("MY_DOMAIN", "")  # Optional

sf_token = sf.login_user_flow(CLIENT_ID, CLIENT_SECRET, MY_DOMAIN)
```

#### Option B: Refresh Token Flow (For User-Specific Access)
This requires storing refresh tokens in a database and using the `get_salesforce_token()` function.

### Step 5: Test the Connection
Create a simple test script to verify the configuration:

```python
from user import salesforce_auth as sf
import toml

try:
    config = toml.load("./.solomo/connections.toml")
    config = config['salesforce_prod']
    
    CLIENT_ID = config["CLIENT_ID"]
    CLIENT_SECRET = config["CLIENT_SECRET"]
    MY_DOMAIN = config.get("MY_DOMAIN", "")
    
    sf_token = sf.login_user_flow(CLIENT_ID, CLIENT_SECRET, MY_DOMAIN)
    print("Salesforce authentication successful!")
    print(f"Access Token: {sf_token.get('access_token', 'Not found')}")
    
except Exception as e:
    print(f"Error: {e}")
```

### Step 6: Configure Connected App Settings (Admin Required)
Ensure the Salesforce admin has configured the Connected App with:

1. **OAuth Scopes**: Include `refresh_token` and `full` scopes
2. **IP Restrictions**: Configure if needed for security
3. **Callback URL**: Set to `https://localhost:1717/OauthRedirect` (or your preferred URL)
4. **API Access**: Enable access to the Salesforce APIs you need

### Step 7: Environment-Specific Configuration
For different environments, create separate configuration sections:

```toml
[salesforce_prod]
# Production settings
sandbox = false

[salesforce_sandbox]
# Sandbox settings
sandbox = true
AUTHORIZATION_BASE_URL = 'https://test.salesforce.com/services/oauth2/authorize'
TOKEN_URL = 'https://test.salesforce.com/services/oauth2/token'
```