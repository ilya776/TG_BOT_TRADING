"""Trading API routes - Execute copy trades and manage positions."""

import logging

from fastapi import APIRouter, HTTPException, status

from app.application.trading.commands import (
    ClosePositionCommand,
    ExecuteCopyTradeCommand,
)
from app.application.trading.dtos import PositionDTO, TradeDTO
from app.presentation.api.dependencies import (
    ClosePositionHandlerDep,
    CurrentUserId,
    ExecuteCopyTradeHandlerDep,
)
from app.presentation.api.v1.schemas.trading_schemas import (
    ClosePositionRequest,
    ErrorResponse,
    ExecuteCopyTradeRequest,
    PositionResponse,
    TradeResponse,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/trading", tags=["Trading"])


# ============================================================================
# EXECUTE COPY TRADE
# ============================================================================


@router.post(
    "/trades",
    response_model=TradeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Execute copy trade",
    description="""
    Execute a copy trade based on a signal.

    **Flow**:
    1. Validate request parameters
    2. Create ExecuteCopyTradeCommand
    3. Execute handler (2-phase commit)
    4. Return trade result

    **2-Phase Commit**:
    - Phase 1: Reserve funds (create PENDING trade)
    - Exchange call (with auto-retry + circuit breaker)
    - Phase 2: Confirm (FILLED + create position) or Rollback (FAILED)

    **Returns**:
    - 201: Trade executed successfully
    - 400: Invalid request parameters
    - 401: Unauthorized (missing/invalid token)
    - 402: Insufficient balance
    - 500: Exchange API error or internal server error
    """,
    responses={
        201: {"model": TradeResponse, "description": "Trade executed successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid request parameters",
        },
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        402: {"model": ErrorResponse, "description": "Insufficient balance"},
        500: {
            "model": ErrorResponse,
            "description": "Exchange API error or internal server error",
        },
    },
)
async def execute_copy_trade(
    request: ExecuteCopyTradeRequest,
    user_id: CurrentUserId,
    handler: ExecuteCopyTradeHandlerDep,
) -> TradeResponse:
    """Execute copy trade endpoint.

    Args:
        request: ExecuteCopyTradeRequest (Pydantic validation).
        user_id: Current user ID (from Authorization header).
        handler: ExecuteCopyTradeHandler (injected dependency).

    Returns:
        TradeResponse з результатом виконання.

    Raises:
        HTTPException: 400, 401, 402, 500 (see above).
    """
    logger.info(
        "api.execute_copy_trade.started",
        extra={
            "user_id": user_id,
            "signal_id": request.signal_id,
            "symbol": request.symbol,
            "size_usdt": str(request.size_usdt),
        },
    )

    try:
        # Create command
        command = ExecuteCopyTradeCommand(
            user_id=user_id,
            signal_id=request.signal_id,
            exchange_name=request.exchange_name,
            symbol=request.symbol,
            side=request.side,
            trade_type=request.trade_type,
            size_usdt=request.size_usdt,
            leverage=request.leverage,
            stop_loss_percentage=request.stop_loss_percentage,
            take_profit_percentage=request.take_profit_percentage,
        )

        # Execute handler
        trade_dto: TradeDTO = await handler.handle(command)

        # Convert DTO → Response
        response = TradeResponse(
            id=trade_dto.id,
            user_id=trade_dto.user_id,
            signal_id=trade_dto.signal_id,
            symbol=trade_dto.symbol,
            side=trade_dto.side,
            trade_type=trade_dto.trade_type,
            status=trade_dto.status,
            size_usdt=trade_dto.size_usdt,
            quantity=trade_dto.quantity,
            leverage=trade_dto.leverage,
            executed_price=trade_dto.executed_price,
            executed_quantity=trade_dto.executed_quantity,
            exchange_order_id=trade_dto.exchange_order_id,
            fee_amount=trade_dto.fee_amount,
            created_at=trade_dto.created_at,
            executed_at=trade_dto.executed_at,
            error_message=trade_dto.error_message,
        )

        logger.info(
            "api.execute_copy_trade.success",
            extra={
                "user_id": user_id,
                "trade_id": trade_dto.id,
                "status": trade_dto.status,
            },
        )

        return response

    except ValueError as e:
        # Business logic errors (insufficient balance, invalid params)
        logger.warning(
            "api.execute_copy_trade.validation_error",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "ValidationError", "message": str(e)},
        )

    except Exception as e:
        # Unexpected errors (exchange API, DB, etc.)
        logger.error(
            "api.execute_copy_trade.error",
            extra={"user_id": user_id, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to execute copy trade. Please try again later.",
            },
        )


# ============================================================================
# CLOSE POSITION
# ============================================================================


@router.post(
    "/positions/{position_id}/close",
    response_model=PositionResponse,
    status_code=status.HTTP_200_OK,
    summary="Close open position",
    description="""
    Close an open position manually.

    **Flow**:
    1. Validate position exists and belongs to user
    2. Create close trade (opposite side)
    3. Execute close on exchange
    4. Update position status to CLOSED
    5. Calculate realized PnL
    6. Return position result

    **Returns**:
    - 200: Position closed successfully
    - 400: Invalid request or position already closed
    - 401: Unauthorized
    - 403: Position doesn't belong to user
    - 404: Position not found
    - 500: Exchange API error or internal server error
    """,
    responses={
        200: {"model": PositionResponse, "description": "Position closed successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid request or position already closed",
        },
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {
            "model": ErrorResponse,
            "description": "Position doesn't belong to user",
        },
        404: {"model": ErrorResponse, "description": "Position not found"},
        500: {
            "model": ErrorResponse,
            "description": "Exchange API error or internal server error",
        },
    },
)
async def close_position(
    position_id: int,
    request: ClosePositionRequest,
    user_id: CurrentUserId,
    handler: ClosePositionHandlerDep,
) -> PositionResponse:
    """Close position endpoint.

    Args:
        position_id: Position ID (from URL path).
        request: ClosePositionRequest (Pydantic validation).
        user_id: Current user ID (from Authorization header).
        handler: ClosePositionHandler (injected dependency).

    Returns:
        PositionResponse з закритою позицією.

    Raises:
        HTTPException: 400, 401, 403, 404, 500 (see above).
    """
    logger.info(
        "api.close_position.started",
        extra={"user_id": user_id, "position_id": position_id},
    )

    # Validate position_id from path matches request body
    if position_id != request.position_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "ValidationError",
                "message": "Position ID in URL doesn't match request body",
            },
        )

    try:
        # Create command
        command = ClosePositionCommand(
            position_id=position_id,
            user_id=user_id,
            exchange_name=request.exchange_name,
        )

        # Execute handler
        position_dto: PositionDTO = await handler.handle(command)

        # Convert DTO → Response
        response = PositionResponse(
            id=position_dto.id,
            user_id=position_dto.user_id,
            symbol=position_dto.symbol,
            side=position_dto.side,
            status=position_dto.status,
            entry_price=position_dto.entry_price,
            quantity=position_dto.quantity,
            leverage=position_dto.leverage,
            stop_loss_price=position_dto.stop_loss_price,
            take_profit_price=position_dto.take_profit_price,
            entry_trade_id=position_dto.entry_trade_id,
            exit_price=position_dto.exit_price,
            exit_trade_id=position_dto.exit_trade_id,
            unrealized_pnl=position_dto.unrealized_pnl,
            realized_pnl=position_dto.realized_pnl,
            opened_at=position_dto.opened_at,
            closed_at=position_dto.closed_at,
        )

        logger.info(
            "api.close_position.success",
            extra={
                "user_id": user_id,
                "position_id": position_id,
                "realized_pnl": str(position_dto.realized_pnl),
            },
        )

        return response

    except ValueError as e:
        # Business logic errors (position not found, already closed, etc.)
        error_msg = str(e).lower()

        if "not found" in error_msg:
            logger.warning(
                "api.close_position.not_found",
                extra={"user_id": user_id, "position_id": position_id},
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "NotFoundError",
                    "message": f"Position {position_id} not found",
                },
            )

        elif "doesn't belong" in error_msg:
            logger.warning(
                "api.close_position.forbidden",
                extra={"user_id": user_id, "position_id": position_id},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "ForbiddenError",
                    "message": "Position doesn't belong to user",
                },
            )

        else:
            logger.warning(
                "api.close_position.validation_error",
                extra={
                    "user_id": user_id,
                    "position_id": position_id,
                    "error": str(e),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "ValidationError", "message": str(e)},
            )

    except Exception as e:
        # Unexpected errors (exchange API, DB, etc.)
        logger.error(
            "api.close_position.error",
            extra={
                "user_id": user_id,
                "position_id": position_id,
                "error": str(e),
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "InternalServerError",
                "message": "Failed to close position. Please try again later.",
            },
        )
