from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AuthContext, get_auth_context, require_csrf
from app.core.responses import ApiResponse, success_response
from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.modules.wallet.schemas import (
    AddMoneyRequest, CreateOrderRequest, CreateOrderResponse, PayDuesRequest,
    PayDuesUpiRequest, PinRequest, SendMoneyRequest, VerifyPaymentRequest,
    VerifyPaymentResponse, WalletMutationResponse, WalletResponse,
    WalletTransactionResponse,
)
from app.modules.wallet.service import WalletService

router = APIRouter(tags=["Wallet"])


@router.get("/wallet", response_model=ApiResponse[WalletResponse])
async def get_wallet(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)):
    return success_response(WalletResponse(**(await WalletService(session).details(context.account))))


@router.get("/wallet/transactions", response_model=ApiResponse[list[WalletTransactionResponse]])
async def get_transactions(context: AuthContext = Depends(get_auth_context), session: AsyncSession = Depends(get_db_session)):
    rows = await WalletService(session).list_transactions(context.account)
    return success_response([WalletTransactionResponse(**row) for row in rows])


@router.post("/wallet/pin", response_model=ApiResponse[WalletMutationResponse])
async def setup_pin(payload: PinRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    async with UnitOfWork(session):
        result = await WalletService(session).setup_pin(context.account, payload)
    return success_response(WalletMutationResponse(**result))


@router.post("/wallet/add-money", response_model=ApiResponse[WalletMutationResponse])
async def add_money(payload: AddMoneyRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    async with UnitOfWork(session):
        result = await WalletService(session).add_money(context.account, payload)
    return success_response(WalletMutationResponse(**result))


@router.post("/wallet/pay-dues", response_model=ApiResponse[WalletMutationResponse])
async def pay_dues(payload: PayDuesRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    async with UnitOfWork(session):
        result = await WalletService(session).pay_dues(context.account, payload)
    return success_response(WalletMutationResponse(**result))


@router.post("/wallet/pay-dues-upi", response_model=ApiResponse[WalletMutationResponse])
async def pay_dues_upi(payload: PayDuesUpiRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    async with UnitOfWork(session):
        result = await WalletService(session).pay_dues_upi(context.account, payload)
    return success_response(WalletMutationResponse(**result))


@router.post("/wallet/send", response_model=ApiResponse[WalletMutationResponse])
async def send_money(payload: SendMoneyRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    async with UnitOfWork(session):
        result = await WalletService(session).send_money(context.account, payload)
    return success_response(WalletMutationResponse(**result))


@router.post("/create-order", response_model=ApiResponse[CreateOrderResponse])
async def create_order(payload: CreateOrderRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    return success_response(CreateOrderResponse(**(await WalletService(session).create_order(context.account, payload))))


@router.post("/verify-payment", response_model=ApiResponse[VerifyPaymentResponse])
async def verify_payment(payload: VerifyPaymentRequest, context: AuthContext = Depends(require_csrf), session: AsyncSession = Depends(get_db_session)):
    return success_response(VerifyPaymentResponse(**(await WalletService(session).verify_payment(context.account, payload))))
