# src/api/main.py
# Copyright (c) Microsoft. All rights reserved.
# Licensed under the MIT license.

import contextlib
import logging
import os
from typing import Union

import fastapi
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

from azure.identity import AzureDeveloperCliCredential, ManagedIdentityCredential
from azure.ai.projects.aio import AIProjectClient

from .util import get_logger

logger = None
enable_trace = False


def _get_env_or_fail(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing environment variable: {name}. "
            f"Define it in .env (dev) or in the environment (prod)."
        )
    return value


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    # Credentials (dev: AzureDeveloperCli; prod: ManagedIdentity)
    azure_credential: Union[AzureDeveloperCliCredential, ManagedIdentityCredential]
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        tenant_id = os.getenv("AZURE_TENANT_ID")
        if tenant_id:
            logger.info("Using AzureDeveloperCliCredential with tenant_id %s", tenant_id)
            azure_credential = AzureDeveloperCliCredential(tenant_id=tenant_id)
        else:
            logger.info("Using AzureDeveloperCliCredential")
            azure_credential = AzureDeveloperCliCredential()
    else:
        user_identity_client_id = os.getenv("AZURE_CLIENT_ID")
        logger.info("Using ManagedIdentityCredential with client_id %s", user_identity_client_id)
        azure_credential = ManagedIdentityCredential(client_id=user_identity_client_id)

    # Required config
    endpoint = _get_env_or_fail("AZURE_EXISTING_AIPROJECT_ENDPOINT")
    chat_deployment = _get_env_or_fail("AZURE_AI_CHAT_DEPLOYMENT_NAME")

    # AI project and chat client
    project = AIProjectClient(credential=azure_credential, endpoint=endpoint)

    # (optional) Azure Monitor tracing
    if enable_trace:
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
            cs = await project.telemetry.get_connection_string()
            if not cs:
                raise RuntimeError("Tracing requested but Application Insights is not enabled.")
            configure_azure_monitor(connection_string=cs)
        except Exception as e:
            logger.error("Failed to configure tracing: %s", e)
            raise

    chat = project.inference.get_chat_completions_client()

    app.state.project = project
    app.state.chat = chat
    app.state.chat_model = chat_deployment

    try:
        yield
    finally:
        try:
            await chat.close()
        except Exception:
            pass
        try:
            await project.close()
        except Exception:
            pass


def create_app():
    if not os.getenv("RUNNING_IN_PRODUCTION"):
        load_dotenv(override=True)

    global logger
    logger = get_logger(
        name="azureaiapp",
        log_level=logging.INFO,
        log_file_name=os.getenv("APP_LOG_FILE"),
        log_to_console=True,
    )

    global enable_trace
    enable_trace = str(os.getenv("ENABLE_AZURE_MONITOR_TRACING", "")).lower() == "true"
    logger.info("Tracing is %s", "enabled" if enable_trace else "not enabled")

    app = fastapi.FastAPI(lifespan=lifespan)

    # opcional; pode remover se não usar arquivos estáticos
    app.mount("/static", StaticFiles(directory="src/api/static"), name="static")

    from . import routes  # registra as rotas
    app.include_router(routes.router)
    return app



