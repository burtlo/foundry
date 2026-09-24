---
name: dotnet-azure-config-migration
description: >-
  Migrates ASP.NET Core appsettings to Azure Key Vault and App Configuration
  at startup (KLv2.Admin pattern): flat key names, pointers-only env files,
  managed identity, local dev. Use when migrating appsettings to Key Vault,
  Azure App Configuration, removing committed secrets, or replicating the
  KLv2.Admin configuration pattern in another .NET repo.
disable-model-invocation: true
---

# .NET Azure Config Migration (Key Vault + App Configuration)

Migrate secrets and settings out of committed `appsettings` into Azure Key Vault and App Configuration. Reference implementation: `KLv2.API/KLv2.Admin/Program.cs`. Validated on `Example.Api`.

## Principles (do not skip)

1. **Flat Key Vault / App Config key names** — use existing Azure names (e.g. `ExampleApiUri`). **Do not** add a `KeyVaultSecretManager` dictionary to remap names; update application code instead.
2. **Pointers-only environment files** — committed `appsettings.{Development,Staging,Production}.json` contain only:
   - `KeyVaultUri` (full vault URI, e.g. `https://{name}.vault.azure.net/`)
   - `AzureAppConfigurationUri` (full App Config URI, e.g. `https://{name}.azconfig.io`)
   - `UseAzureAppConfiguration` (bool, per-env rollout flag)
   - logging sections
3. **Secrets vs non-secrets**
   - **Key Vault**: client secrets, function keys, connection strings with credentials
   - **App Config**: URIs, tenant IDs, client IDs, feature flags, email addresses
   - App Config may use **Key Vault references** for secrets (requires `ConfigureKeyVault` on the App Config provider)
4. **CI/CD unchanged** — pipeline builds/publishes a zip only. Config loads at **App Service runtime** via managed identity.
5. **`launchSettings.json` is local-only** — never deployed. Do not put service settings there; only `ASPNETCORE_ENVIRONMENT` and optional local overrides (see Local dev).
6. **Pointer URIs stay in committed appsettings** — do not add `KeyVaultUri` or `AzureAppConfigurationUri` to App Service portal settings unless intentionally overriding the deployed zip.

## Workflow checklist

Copy and track progress:

```
Migration Progress:
- [ ] Phase 1: Inventory & map keys
- [ ] Phase 2: Azure prerequisites verified
- [ ] Phase 3: Code changes (Program.cs, packages, Bind classes)
- [ ] Phase 4: Slim appsettings + gitignore Local.json
- [ ] Phase 5: Update code references to flat keys
- [ ] Phase 6: Build & test
- [ ] Phase 7: Verify Azure stores populated
- [ ] Phase 8: Local smoke test
- [ ] Phase 9: Update AGENTS.md / docs
```

---

## Phase 1: Inventory & map keys

1. Read all `appsettings*.json` and grep for `configuration["`, `GetValue`, `GetSection`, `IOptions`, and nested keys (`Okta:`, `ApiSettings:`, etc.).
2. List every setting the app reads at runtime.
3. For each setting, decide **Key Vault** vs **App Config** vs **portal-only** (e.g. `APPLICATIONINSIGHTS_CONNECTION_STRING`, `ASPNETCORE_ENVIRONMENT`).
4. Map old nested names → flat Azure names. Confirm names against **existing** Key Vault secrets and App Config keys (`az keyvault secret list`, `az appconfig kv list`) — do not invent new names if stores already use a convention.
5. Document per-environment resource names (vault, app config store, app service) before editing code.

---

## Phase 2: Azure prerequisites (verify with CLI)

Run checks in [azure-verification.md](azure-verification.md). Confirm before merging:

| Prerequisite | Dev | QA | Prod |
|--------------|-----|-----|------|
| App Service system-assigned MI enabled | | | |
| Key Vault Secrets Officer on MI | | | |
| App Configuration Data Reader on MI | | | |
| Required secrets in Key Vault | | | |
| Required keys in App Config | | | |
| `ASPNETCORE_ENVIRONMENT` on App Service matches `appsettings.{Env}.json` | | | |

Enable `UseAzureAppConfiguration: true` **per environment** only after that environment's App Config is populated.

---

## Phase 3: Code changes

### NuGet packages (project `.csproj`)

```xml
<PackageReference Include="Azure.Extensions.AspNetCore.Configuration.Secrets" Version="1.*" />
<PackageReference Include="Azure.Identity" Version="1.*" />
<PackageReference Include="Microsoft.Extensions.Configuration.AzureAppConfiguration" Version="8.*" />
```

### `Program.cs` — configuration bootstrap

Add after `WebApplication.CreateBuilder(args)`:

```csharp
builder.Host.ConfigureAppConfiguration((hostContext, config) =>
{
    var interimConfig = config.Build();

    if (interimConfig.GetValue<bool>("UseAzureAppConfiguration", false)
        && !string.IsNullOrEmpty(interimConfig["AzureAppConfigurationUri"]))
    {
        var azureCredential = new DefaultAzureCredential(true);
        config.AddAzureAppConfiguration(options =>
        {
            options.Connect(
                new Uri(interimConfig["AzureAppConfigurationUri"]!),
                azureCredential)
                .ConfigureKeyVault(kv => kv.SetCredential(azureCredential));
        });
    }

    var keyVaultUri = interimConfig["KeyVaultUri"];
    if (!string.IsNullOrEmpty(keyVaultUri))
    {
        config.AddAzureKeyVault(
            new Uri(keyVaultUri),
            new DefaultAzureCredential(true));
    }

#if DEBUG
    config.AddJsonFile("appsettings.Local.json", optional: true, reloadOnChange: true);
#endif
});
```

**Precedence** (later wins): `appsettings` → env vars → App Config → Key Vault → `appsettings.Local.json` (DEBUG).

### Configuration bind classes

Create `Configuration/{Service}Configuration.cs` with static `Bind(IConfiguration)` methods. Inline flat key string literals in `Bind()` — avoid a shared `AppSettingKeys` constants file unless the repo already uses one.

Replace all `configuration["Okta:Domain"]` / `GetSection("ApiSettings")` usage with flat keys.

---

## Phase 4: Appsettings & gitignore

### `appsettings.Development.json` (example)

```json
{
  "Logging": { "LogLevel": { "Default": "Information", "Microsoft": "Warning" } },
  "KeyVaultUri": "https://{env}-kv-{team}-north.vault.azure.net/",
  "AzureAppConfigurationUri": "https://{env}-ac-{team}-north.azconfig.io",
  "UseAzureAppConfiguration": true
}
```

QA/Prod: same shape; set `UseAzureAppConfiguration: false` until App Config is ready.

### Local dev files

- Add `**/appsettings.Local.json` to `.gitignore`
- Add `appsettings.Local.json.example` with `Auth:Mock` block and placeholder flat keys (no real secrets)
- Do **not** commit pull/helper scripts unless the team wants them in the repo

### `launchSettings.json`

- Keep only `ASPNETCORE_ENVIRONMENT` per profile
- Optional **`Development-Local`** profile with `UseAzureAppConfiguration=false` when developers lack App Config Data Reader RBAC
- Never put service URLs, secrets, or feature flags in launch profiles

---

## Phase 5: Replace config reads in app code

Grep and update:

- `configuration["Nested:Key"]` → flat key
- `IOptions<T>` sections bound to nested appsettings → `*Configuration.Bind(configuration)`
- `ConfigurationManager.GetValue` in Razor/components → same flat keys
- Authentication extensions, HTTP client setup, Power BI / Okta registration

---

## Phase 6: Build & test

```bash
dotnet restore
dotnet build
dotnet test
```

Fix binding errors (`ConfigurationException: No Uri configuration set`) by confirming keys exist in the configuration chain.

---

## Phase 7: Deployed behavior

After push to Azure:

1. GitHub Actions builds and deploys zip — **no** Key Vault/App Config access in CI
2. App Service starts → reads `appsettings.{Environment}.json` from zip
3. Portal `ASPNETCORE_ENVIRONMENT` selects the env file
4. Managed identity loads App Config (if enabled) then Key Vault
5. Legacy portal app settings with **old key names** are ignored (harmless orphans). Remove optionally: `ActionsFromEmailAddress`, `ClaimsPageEnabled`, nested `UIAdminSettings:*`, etc.

**Do not** duplicate secrets in portal app settings under new flat names unless intentionally overriding (Key Vault still wins for same key).

---

## Phase 8: Local development

| Approach | When |
|----------|------|
| `Development` profile | Developer has App Config Data Reader + KV access; matches deployed dev |
| `Development-Local` profile | `UseAzureAppConfiguration=false`; values from KV + `appsettings.Local.json` |
| `az login` | Required for `DefaultAzureCredential` locally |

**Common local failure**: 403 on App Config with personal account while `az appconfig` CLI works (CLI uses access keys). Fix: grant **App Configuration Data Reader** to the developer, or use `Development-Local`.

Mock auth (`Auth:Mock:Enabled` in `appsettings.Local.json`) avoids Okta redirect issues on localhost.

---

## Phase 9: Documentation

Update repo `AGENTS.md`:

- Config load order and pointer keys
- Flat key table (key → purpose → KV or App Config)
- Local dev steps (`appsettings.Local.json.example`, launch profiles)
- Note CI/CD does not need workflow changes

---

## Anti-patterns

| Avoid | Do instead |
|-------|------------|
| `KeyVaultSecretManager` name mapping | Change code to flat KV names |
| Secrets in committed appsettings | KV / App Config KV refs |
| Service settings in `launchSettings.json` | App Config / KV / Local.json |
| Pointer URIs in App Service portal settings | Committed `appsettings.{Environment}.json` in deploy zip |
| Enabling App Config in QA/Prod before stores populated | Feature flag per env |
| Assuming GitHub Actions needs KV access | Runtime MI on App Service only |
| Renaming existing App Config URI keys in Azure | Align code to existing names |

---

## Additional resources

- Azure CLI verification commands: [azure-verification.md](azure-verification.md)
- Example.Api reference: `Daniel/TICKET-2452` branch
- KLv2.Admin reference: `KLv2.API/KLv2.Admin/Program.cs`

## Kickoff

```text
Migrate this app's appsettings to Azure Key Vault and App Configuration.

@github-private/.cursor/skills/dotnet-azure-config-migration/SKILL.md
```

Reference `KLv2.API/KLv2.Admin/Program.cs` when a concrete pattern is needed.
