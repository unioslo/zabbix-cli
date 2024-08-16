# Authentication

Zabbix-cli provides several ways to authenticate. They are tried in the following order:

1. [API token in config file](#api-token)
2. [API token in file (if `use_auth_token_file=true`)](#auth-token-file)
3. [Username and password in config file](#config-file)
4. [Username and password in auth file](#auth-file)
5. [Username and password in environment variables](#environment-variables)
6. [Username and password from prompt](#prompt)

## Username and Password

Username and password-based authentication is the default and easiest way to authenticate, but also the least secure.

### Config file

The password can be set directly in the config file:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
password = "zabbix"
```

### Prompt

By omitting the `password` parameter in the config file or all other authentication methods fail, you will be prompted for a password when running zabbix-cli:

```toml
[api]
zabbix_url = "https://zabbix.example.com/"
username = "Admin"
```

### Auth file

An auth file named `.zabbix-cli_auth` can be created in the user's home directory. The content of this file should be in the `USERNAME::PASSWORD` format.

```bash
echo "Admin::zabbix" > ~/.zabbix-cli_auth
```

The file is automatically loaded if it exists. The location of the file can be changed in the config file:

```toml
[app]
auth_file = "~/.zabbix-cli_auth"
```

### Environment variables

The username and password can be set as environment variables:

```bash
export ZABBIX_USERNAME="Admin"
export ZABBIX_PASSWORD="zabbix"
```

These are automatically loaded if the `password` parameter is not set in the config file.

## Auth token file

Once you have authenticated with a username and password, zabbix-cli will store a session token if you configure `use_auth_token_file=true` in the config. This way you don't need to provide your credentials each time you run zabbix-cli. The token file should also be secured properly with 600 permissions.

```toml
[app]
use_auth_token_file = true
```

The location of the auth token file can be changed in the config file:

```toml
[app]
auth_token_file = "/path/to/auth/token/file"
```

## API token

Zabbix-cli also supports authentication with an API token specified directly in the config file:

```toml
[api]
auth_token = "API_TOKEN"

[app]
use_auth_token_file = false
```
