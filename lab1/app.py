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
    client = SecretClient(vault_url=VAULT_URL,credential=credential)
    secreto = client.get_secret("mi-secreto")
    return {"valor": secreto.value}

    