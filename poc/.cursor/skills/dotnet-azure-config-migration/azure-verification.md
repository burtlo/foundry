# Azure Verification Commands

Use `az login` first. IoT apps span subscriptions: Dev (`QA/DEV`), QA (`QA`), Prod (`Production`).

## App Service managed identity

```text
az webapp show -n {app-name} -g {rg} --subscription "{sub}" --query "{name:name, principalId:identity.principalId, type:identity.type}" -o json
```

Expect `type: SystemAssigned` and non-null `principalId`.

## RBAC on Key Vault and App Config

```text
az keyvault show -n {vault-name} --subscription "{sub}" --query id -o tsv
az appconfig show -n {app-config-name} --subscription "{sub}" --query id -o tsv
az role assignment list --assignee-object-id {principal-id} --scope {kv-scope} --query "[].roleDefinitionName" -o tsv
az role assignment list --assignee-object-id {principal-id} --scope {ac-scope} --query "[].roleDefinitionName" -o tsv
```

Required roles on App Service MI:
- **Key Vault Secrets Officer** (or Secrets User) on the vault
- **App Configuration Data Reader** on the config store

## Developer local access (optional)

```text
az appconfig kv list --name {store} --key "{prefix}*" --auth-mode login -o json
```

`403` = developer needs **App Configuration Data Reader** (CLI `az appconfig` may still work via access keys).

## List existing keys (align code to these names)

```text
az keyvault show -n {vault-name} --subscription "{sub}" --query properties.vaultUri -o tsv
az appconfig show -n {app-config-name} --subscription "{sub}" --query endpoint -o tsv
az keyvault secret list --vault-name {vault-name} --query "[].name" -o tsv
az appconfig kv list -n {app-config-name} --key "{prefix}*" -o table
```

Use the vault URI and App Config endpoint when populating `KeyVaultUri` and `AzureAppConfigurationUri` in `appsettings.{Environment}.json`.

## Portal app settings audit

```text
az webapp config appsettings list -n {app-name} -g {rg} --subscription "{sub}" --query "[].name" -o tsv
```

Flag legacy nested names (`Okta:`, `ZuulSettings:`, `ActionsFromEmailAddress`) — new code won't read them. Pointer URIs (`KeyVaultUri`, `AzureAppConfigurationUri`) should **not** be required in portal settings.

## App Service environment

```text
az webapp config appsettings list -n {app-name} -g {rg} --subscription "{sub}" --query "[?name=='ASPNETCORE_ENVIRONMENT'].value" -o tsv
```

Must match committed `appsettings.{Environment}.json` filename:
- `Development` → `appsettings.Development.json`
- `Staging` → `appsettings.Staging.json` (QA)
- `Production` → `appsettings.Production.json`

## Config gap report template

After listing KV + App Config, produce a table for the user:

| Flat key | Purpose | Dev | QA | Prod | Store |
|----------|---------|-----|-----|------|-------|
| `{AppPrefix}OktaClientSecret` | Okta secret | ✓ | ✗ | ✗ | KV |
| `{AppPrefix}ZuulUri` | API base URL | ✓ | ✓ | ✗ | App Config |

Mark missing keys before enabling `UseAzureAppConfiguration` in that environment.
