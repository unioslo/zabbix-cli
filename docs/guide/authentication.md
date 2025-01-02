# Authentication

Zabbix-cli provides several ways to authenticate. They are tried in the following order:

1. [Token - Environment variables](#environment-variables)
1. [Token - Config file](#config-file)
1. [Token - Auth token file](#auth-token-file)
1. [Password - Environment variables](#environment-variables_1)
1. [Password - Config file](#config-file_1)
1. [Password - Auth file](#auth-file)
1. [Password - Prompt](#prompt)

## Token

The application supports authenticating with an API or session token. API tokens are created in the Zabbix frontend or via `zabbix-cli create_token`. A session token is obtained by logging in to the Zabbix API with a username and password.

!!! info "Session vs API token"
    Semantically, a session token and API token are the same thing from an API authentication perspective. They are both sent as the `auth` parameter in the Zabbix API requests.

### Environment variables

The API token can be set as an environment variable:

```bash
export ZABBIX_API_TOKEN="API TOKEN"
```

### Config file

The token can be set directly in the config file:

```toml
[api]
auth_token = "API_TOKEN"
```

### Auth token file

The application can store and reuse session tokens between runs. This feature is enabled by default and configurable via the following options:

```toml
[app]
# Enable token file storage (default: true)
use_session_file = true

# Customize token file location (optional)
auth_token_file = "/path/to/auth/token/file"

# Enforce secure file permissions (default: true, no effect on Windows)
allow_insecure_auth_file = false
```

**How it works:**

- Log in once with username and password
- Token is automatically saved to the file
- Subsequent runs will use the saved token for authentication

When `allow_insecure_auth_file` is set to `false`, the application will attempt to set `600` (read/write for owner only) permissions on the token file when creating/updating it.

## Username and Password

The application supports authenticating with a username and password. The password can be set in the config file, an auth file, as environment variables, or prompted for when starting the application.

### Environment variables

The username and password can be set as environment variables:

```bash
export ZABBIX_USERNAME="Admin"
export ZABBIX_PASSWORD="zabbix"
```

### Config file

The password can be set directly in the config file:

```toml
[api]
username = "Admin"
password = "zabbix"
```

### Auth file

A file named `.zabbix-cli_auth` can be created in the user's home directory or in the application's data directory. The file should contain a single line of text in the format `USERNAME::PASSWORD`.

```bash
echo "Admin::zabbix" > ~/.zabbix-cli_auth
```

The location of the auth file file can be changed in the config file:

```toml
[app]
auth_file = "~/.zabbix-cli_auth"
```

### Prompt

When all other authentication methods fail, the application will prompt for a username and password. The default username in the prompt can be configured:

```toml
[api]
username = "Admin"
```

## URL

The URL of the Zabbix API can be set in the config file, as an environment variable, or prompted for when starting the application.

They are processed in the following order:

1. [Environment variables](#environment-variables_2)
1. [Config file](#config-file_2)
1. [Prompt](#prompt_1)

The URL should not include `/api_jsonrpc.php`.

### Config file

The URL of the Zabbix API can be set in the config file:

```toml

[api]
url = "http://zabbix.example.com"
```

### Environment variables

The URL can also be set as an environment variable:

```bash
export ZABBIX_URL="http://zabbix.example.com"
```

### Prompt

When all other methods fail, the application will prompt for the URL of the Zabbix API.
