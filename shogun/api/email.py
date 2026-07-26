"""Email routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_email_service
from shogun.schemas.channels import (
    EmailAccountCreate,
    EmailAccountPermissionsUpdate,
    EmailAccountResponse,
    EmailAccountUpdate,
    EmailComposeRequest,
    EmailMessageFull,
    EmailTestResponse,
)
from shogun.schemas.common import ApiResponse
from shogun.services.comms_permissions import effective_account_permissions
from shogun.services.email_service import EmailService

router = APIRouter(prefix="/channels/email", tags=["Email"])


async def _account_response(acc) -> EmailAccountResponse:
    response = EmailAccountResponse.model_validate(acc)
    return response.model_copy(update=await effective_account_permissions())


@router.get("/account", response_model=ApiResponse[EmailAccountResponse | None])
async def get_account(email_svc: EmailService = Depends(get_email_service)):
    acc = await email_svc.get_account()
    if not acc:
        return ApiResponse(data=None)
    return ApiResponse(data=await _account_response(acc))


@router.post("/account", response_model=ApiResponse[EmailAccountResponse])
async def configure_account(
    body: EmailAccountCreate,
    email_svc: EmailService = Depends(get_email_service),
):
    acc = await email_svc.configure_account(body)
    return ApiResponse(data=await _account_response(acc))


@router.patch("/account", response_model=ApiResponse[EmailAccountResponse])
async def update_account(
    body: EmailAccountUpdate,
    email_svc: EmailService = Depends(get_email_service),
):
    acc = await email_svc.get_account()
    if not acc:
        raise HTTPException(status_code=404, detail="No email account configured")

    from shogun.services.email_service import encrypt_password
    kwargs = body.model_dump(exclude_unset=True)
    if "password" in kwargs:
        pwd = kwargs.pop("password")
        if pwd:
            kwargs["encrypted_password"] = encrypt_password(pwd)

    # Perform updates
    for k, v in kwargs.items():
        if hasattr(acc, k):
            setattr(acc, k, v)

    await email_svc.session.flush()
    await email_svc.session.commit()
    return ApiResponse(data=await _account_response(acc))


@router.delete("/account", response_model=ApiResponse[bool])
async def remove_account(email_svc: EmailService = Depends(get_email_service)):
    ok = await email_svc.remove_account()
    return ApiResponse(data=ok)


@router.patch(
    "/account/permissions",
    response_model=ApiResponse[EmailAccountResponse],
    deprecated=True,
)
async def update_permissions(
    _body: EmailAccountPermissionsUpdate,
    _email_svc: EmailService = Depends(get_email_service),
):
    raise HTTPException(
        status_code=410,
        detail="Account scopes moved to ToolGate > Capability boundaries > Comms.",
    )


@router.post("/account/test", response_model=ApiResponse[EmailTestResponse])
async def test_connection(
    body: EmailAccountCreate,
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.test_connection(body)
    return ApiResponse(data=EmailTestResponse(**res))


@router.get("/account/folders", response_model=ApiResponse[list[str]])
async def get_folders(email_svc: EmailService = Depends(get_email_service)):
    folders = await email_svc.fetch_folders()
    return ApiResponse(data=folders)


@router.get("/account/messages", response_model=ApiResponse[dict[str, Any]])
async def get_messages(
    folder: str = "INBOX",
    page: int = 1,
    per_page: int = 20,
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.fetch_messages(folder=folder, page=page, per_page=per_page)
    return ApiResponse(data=res)


@router.get("/account/messages/{uid}", response_model=ApiResponse[EmailMessageFull])
async def get_message(
    uid: str,
    folder: str = "INBOX",
    email_svc: EmailService = Depends(get_email_service),
):
    msg = await email_svc.fetch_message(uid=uid, folder=folder)
    return ApiResponse(data=EmailMessageFull(**msg))


@router.post("/account/send", response_model=ApiResponse[dict[str, Any]])
async def send_email(
    body: EmailComposeRequest,
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.send_email(body)
    return ApiResponse(data=res)


@router.post("/account/messages/{uid}/read", response_model=ApiResponse[dict[str, Any]])
async def mark_read(
    uid: str,
    folder: str = "INBOX",
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.mark_read(uid=uid, folder=folder, read=True)
    return ApiResponse(data=res)


@router.post("/account/messages/{uid}/unread", response_model=ApiResponse[dict[str, Any]])
async def mark_unread(
    uid: str,
    folder: str = "INBOX",
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.mark_read(uid=uid, folder=folder, read=False)
    return ApiResponse(data=res)


@router.delete("/account/messages/{uid}", response_model=ApiResponse[dict[str, Any]])
async def delete_message(
    uid: str,
    folder: str = "INBOX",
    email_svc: EmailService = Depends(get_email_service),
):
    res = await email_svc.delete_message(uid=uid, folder=folder)
    return ApiResponse(data=res)
