



## Lab 1 - completado
Key Vault: kv-labs-rafa-01
Secreto: mi-secreto = hola-mundo-123
Identity: id-chatbot-lab
  clientId:    f507c956-8bb5-4145-a828-ac19f9e969df
  principalId: 3d8d64f8-99d3-4a10-b60c-cdd444234fdd
  rol: Key Vault Secrets User sobre el vault


  # Lab 1 — Identidad sin contraseñas

Una app en Azure lee un secreto de un Key Vault usando una managed identity. Sin contraseñas en el código, en la imagen ni en las variables de entorno.

| | |
|---|---|
| Resource group | `rg-labs-devops` |
| Región | `eastus2` |
| Estado | Actos 1–3 completados · Acto 4 (SQL) pendiente |

---

## Arquitectura

```
        Managed identity (id-chatbot-lab)
                    │  asignada a
                    ▼
          Container App (app-secreto)
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
 Container Registry         Key Vault
   (rol AcrPull)        (rol Secrets User)
```

La flecha de arriba es la asignación. Las dos de abajo son la identidad usándose: para bajar la imagen y para leer el secreto.

---

## Recursos creados

| Recurso | Nombre | Rol asignado |
|---|---|---|
| Key Vault | `kv-labs-rafa-01` | — |
| Managed identity | `id-chatbot-lab` | `Key Vault Secrets User` sobre el vault |
| | | `AcrPull` sobre el registry |
| Container Registry | `acrlabsrafa01` | — |
| Container Apps Env | `env-labs` | — |
| Container App | `app-secreto` | — |

```
clientId:    f507c956-8bb5-4145-a828-ac19f9e969df
principalId: 3d8d64f8-99d3-4a10-b60c-cdd444234fdd
```

Secreto de prueba: `mi-secreto` = `hola-mundo-123`

---

## Pasos ejecutados

### Acto 1 — Key Vault

```powershell
$kv = "kv-labs-rafa-01"
az keyvault create --name $kv --resource-group rg-labs-devops --location eastus2 --enable-rbac-authorization true
$kvId = az keyvault show --name $kv --query id -o tsv

# Este falla con Forbidden aunque seas Owner. Es el punto del lab.
az keyvault secret set --vault-name $kv --name mi-secreto --value "hola-mundo-123"

$me = az ad signed-in-user show --query id -o tsv
az role assignment create --assignee $me --role "Key Vault Secrets Officer" --scope $kvId
# esperar 2 minutos

az keyvault secret set --vault-name $kv --name mi-secreto --value "hola-mundo-123"
```

### Acto 2 — Managed identity

```powershell
az identity create --name id-chatbot-lab --resource-group rg-labs-devops --location eastus2

$idClientId    = az identity show -g rg-labs-devops -n id-chatbot-lab --query clientId -o tsv
$idPrincipalId = az identity show -g rg-labs-devops -n id-chatbot-lab --query principalId -o tsv
$idResourceId  = az identity show -g rg-labs-devops -n id-chatbot-lab --query id -o tsv

az role assignment create --assignee $idPrincipalId --role "Key Vault Secrets User" --scope $kvId
```

`Secrets User`, no `Officer`: puede leer, no puede crear ni borrar.

### Acto 3 — App que usa la identidad

```powershell
$acr = "acrlabsrafa01"
az acr create --name $acr --resource-group rg-labs-devops --location eastus2 --sku Basic
az containerapp env create --name env-labs --resource-group rg-labs-devops --location eastus2

az acr login --name $acr
docker build -t "$acr.azurecr.io/chatbot-lab:v1" .
docker push "$acr.azurecr.io/chatbot-lab:v1"

az role assignment create --assignee $idPrincipalId --role "AcrPull" --scope (az acr show --name $acr --query id -o tsv)

az containerapp create --name app-secreto --resource-group rg-labs-devops --environment env-labs `
  --image "$acr.azurecr.io/chatbot-lab:v1" --registry-server "$acr.azurecr.io" `
  --registry-identity $idResourceId --user-assigned $idResourceId `
  --env-vars "VAULT_URL=https://$kv.vault.azure.net/" "AZURE_CLIENT_ID=$idClientId" `
  --ingress external --target-port 8000 --min-replicas 1
```

Prueba: `https://<fqdn>/secreto` devuelve `{"valor":"hola-mundo-123"}`

---

## Código

`app.py`

```python
import os
from fastapi import FastAPI
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

app = FastAPI()

VAULT_URL = os.environ["VAULT_URL"]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/secreto")
def leer_secreto():
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=VAULT_URL, credential=credential)
    secreto = client.get_secret("mi-secreto")
    return {"valor": secreto.value}
```

`requirements.txt`

```
fastapi
uvicorn
azure-identity
azure-keyvault-secrets
```

`Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Ninguna credencial. Solo `DefaultAzureCredential()`.

---

## Recuperar el contexto

Al cerrar PowerShell se pierden las variables:

```powershell
az login
cd C:\Users\rafa\renting-chatbot-labs\lab1

$kv  = "kv-labs-rafa-01"
$acr = "acrlabsrafa01"
$kvId          = az keyvault show --name $kv --query id -o tsv
$idClientId    = az identity show -g rg-labs-devops -n id-chatbot-lab --query clientId -o tsv
$idPrincipalId = az identity show -g rg-labs-devops -n id-chatbot-lab --query principalId -o tsv
$idResourceId  = az identity show -g rg-labs-devops -n id-chatbot-lab --query id -o tsv

echo $kv; echo $acr; echo $idClientId; echo $idResourceId
```

## Redesplegar tras cambiar el código

```powershell
docker build --no-cache -t "$acr.azurecr.io/chatbot-lab:vN" .
docker push "$acr.azurecr.io/chatbot-lab:vN"
az containerapp update -n app-secreto -g rg-labs-devops --image "$acr.azurecr.io/chatbot-lab:vN"
```

Subir el número de tag en cada despliegue. Reusar el mismo hace que Container Apps se quede con la imagen vieja.

## Diagnóstico

```powershell
az containerapp logs show -n app-secreto -g rg-labs-devops --tail 40

az containerapp revision list -n app-secreto -g rg-labs-devops `
  --query "[].{rev:name, activa:properties.active, estado:properties.runningState}" -o table
```

---

## Lo aprendido

### 1. Azure separa el plano de control del plano de datos

| Plano | Qué permite | Rol |
|---|---|---|
| Control | crear, borrar, configurar el recurso | Owner, Contributor |
| Datos | leer y escribir el contenido | Key Vault Secrets User / Officer |

Ser Owner de la suscripción y haber creado el vault no da acceso a sus secretos. Aplica igual a Storage, SQL y Cosmos. Si vienes de AWS, es la diferencia más grande: allá `AdministratorAccess` da todo.

### 2. Una identidad puede existir sin contraseña

`id-chatbot-lab` no tiene usuario ni clave. Tiene dos identificadores que se confunden siempre:

- **clientId** — lo usa el código para decir "quiero autenticarme como esta identidad"
- **principalId** — lo usa Azure para asignarle roles

### 3. Los permisos tardan en propagarse

De 1 a 5 minutos. El propio error lo advierte: *"please observe propagation time"*. Sin saberlo, uno termina cambiando cosas que estaban bien.

### 4. Mínimo privilegio se aplica eligiendo el rol correcto

`Secrets User` en vez de `Officer` es la diferencia entre "comprometen la identidad y leen un secreto" y "comprometen la identidad y borran el vault".

### 5. DefaultAzureCredential hace el código portable

Prueba fuentes en orden hasta encontrar una válida: variables de entorno, managed identity, el login de `az`, VS Code. El mismo `app.py` corre en local y en producción sin cambiar una línea.

`AZURE_CLIENT_ID` es obligatoria cuando hay una user-assigned identity: sin ella la librería no sabe cuál elegir.

### 6. Leer errores y logs

- `Assignment: (not found)` significa que el rol no existe, no que esté propagándose
- El error trae la acción y el recurso exactos
- Los logs del contenedor son la primera parada, no la última
- `CACHED [5/5] COPY app.py .` significa que Docker está construyendo la versión vieja → usar `--no-cache`

### 7. PowerShell no avisa de variables vacías

Una variable vacía desaparece del comando en vez de dar error:

```powershell
# escrito
az role assignment create --assignee $me --role "..." --scope $kvId
# recibido si $me está vacía
az role assignment create --assignee --role "..." --scope $kvId
```

Hábito: `echo` después de definir cualquier variable, antes de usarla.

---

## Cómo se traduce al proyecto

| Del lab | En Renting |
|---|---|
| La identidad leyendo el vault | El agente de Foundry autenticándose contra el MCP |
| El rol de solo lectura | El MCP con `db_datareader` sobre SQL, nunca escritura |
| Pull del ACR con identidad | Cómo Foundry baja la imagen del agente |

---

## Problemas encontrados

**ACR Tasks no está disponible en suscripciones trial.** Tanto `az acr build` como `az containerapp up --source` fallan con `TasksOperationsNotAllowed`. Se resolvió construyendo con Docker local.

Es probable que las cuotas de modelos de Foundry tengan una restricción parecida en el Lab 3, y esa no tiene rodeo. Pedir un resource group en la suscripción de Renting con `Contributor` + `User Access Administrator`.

**Docker Desktop no arranca solo.** Hay que abrirlo a mano antes de construir.

---

## Pendiente — Acto 4

Azure SQL con administrador de Entra ID:

```sql
CREATE USER [id-chatbot-lab] FROM EXTERNAL PROVIDER;
ALTER ROLE db_datareader ADD MEMBER [id-chatbot-lab];
```

La app consulta la base sin cadena de conexión con usuario y clave. Es exactamente cómo el MCP Data va a hablar con SQL en el proyecto.

## Limpieza

```powershell
# Apagar la app cuando no se use
az containerapp update -n app-secreto -g rg-labs-devops --min-replicas 0

# Registry basura del intento fallido con containerapp up
az acr delete --name caac3192d6c2acr --resource-group rg-labs-devops --yes
```